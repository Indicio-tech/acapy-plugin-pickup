"""Delivery Request and wrapper message for Pickup Protocol."""

import logging
from typing import Optional, Sequence, Set, cast

from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from aries_cloudagent.transport.inbound.manager import InboundTransportManager
from aries_cloudagent.transport.inbound.session import InboundSession
from aries_cloudagent.transport.wire_format import BaseWireFormat
from pydantic import Field
from typing_extensions import Annotated

from ..acapy import AgentMessage, Attach
from ..acapy.error import HandlerException
from ..undelivered_queue.base import UndeliveredInterface, message_id_for_outbound
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
        queue = context.inject(UndeliveredInterface)

        key = context.message_receipt.sender_verkey
        message_attachments = []

        if queue.has_message_for_key(key):

            async with context.session() as profile_session:

                for msg in queue.get_messages_for_key(key=key, count=self.limit):

                    recipient_key = (
                        msg.target_list[0].recipient_keys
                        or context.message_receipt.recipient_verkey
                    )
                    routing_keys = msg.target_list[0].routing_keys or []
                    sender_key = msg.target_list[0].sender_key or key

                    # This scenario is rare; a message will almost always have an
                    # encrypted payload. The only time it won't is if we're sending a
                    # message from the mediator itself, rather than forwarding a message
                    # from another agent.
                    # TODO: update ACA-Py to store all messages with an
                    # encrypted payload
                    if not msg.enc_payload:
                        msg.enc_payload = await wire_format.encode_message(
                            profile_session,
                            msg.payload,
                            recipient_key,
                            routing_keys,
                            sender_key,
                        )

                    attached_msg = Attach.data_base64(
                        ident=message_id_for_outbound(msg), value=msg.enc_payload
                    )
                    message_attachments.append(attached_msg)

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

        queue = context.inject(UndeliveredInterface)
        key = context.message_receipt.sender_verkey

        if queue.has_message_for_key(key):
            queue.remove_messages_for_key(key=key, msg=self.message_id_list)

        response = Status(message_count=queue.message_count_for_key(key))
        response.assign_thread_from(self)
        await responder.send_reply(response)
