from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder

from ..acapy import AgentMessage

PROTOCOL = "https://didcomm.org/messagepickup/2.0"


# This is the start of a message updating the Live Delivery status
# Will require a deeper analysis of ACA-Py to fully implement
class LiveDeliveryChange(AgentMessage):
    """Live Delivery Change message."""

    message_type = f"{PROTOCOL}/live-delivery-change"

    live_delivery: bool = False

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle LiveDeliveryChange message"""
        return await super().handle(context, responder)
