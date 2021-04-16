"""Simple Agent Message class."""

import logging
from abc import ABC
from typing import Any, Mapping, Optional

from aries_cloudagent.messaging.base_handler import BaseHandler
from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from pydantic import BaseModel, parse_obj_as
from pydantic.fields import Field
from typing_extensions import Annotated
from uuid import uuid4


LOGGER = logging.getLogger(__name__)


class Thread(BaseModel):
    thid: Annotated[
        Optional[str],
        Field(
            description="Thread identifier",
            examples=[uuid4()],  # typically a UUID4 but not necessarily
        ),
    ] = None
    pthid: Annotated[
        Optional[str],
        Field(
            description="Parent thread identifier",
            examples=[uuid4()],  # typically a UUID4 but not necessarily
        ),
    ] = None
    sender_order: Annotated[
        Optional[int],
        Field(
            description="Ordinal of message among all from current sender in thread",
            examples=[11, 0, 2],
        ),
    ] = None
    received_orders: Annotated[
        Optional[
            dict[
                Annotated[str, Field(description="Sender key")],
                Annotated[
                    int, Field(description="Highest sender_order value for sender")
                ],
            ]
        ],
        Field(
            description="Highest sender_order value that sender has seen from "
            "others on thread"
        ),
    ] = None


class AgentMessage(BaseModel, ABC):
    """AgentMessage Interface Definition."""

    id: Annotated[str, Field(alias="@id")]
    type: Annotated[str, Field(alias="@type")]
    thread: Optional[Thread] = None

    @classmethod
    def deserialize(cls, value: Mapping[str, Any]) -> "AgentMessage":
        """Deserialize an instance of message."""
        return parse_obj_as(cls, value)

    def serialize(self) -> dict:
        """Serialize an instance of message to dictionary."""
        return self.dict(exclude_none=True, by_alias=True)

    def assign_thread_from(self, msg: "AgentMessage"):
        """Assign thread info from another message."""
        if msg:
            thread = msg.thread
            thid = thread.thid if thread else msg.id
            pthid = thread and thread.pthid
            self.assign_thread_id(thid, pthid)

    def assign_thread_id(self, thid: str = None, pthid: str = None):
        """Assign thread info."""
        if thid or pthid:
            self.thread = Thread(thid=thid, pthid=pthid)
        else:
            self.thread = None

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle a message of this type."""
        LOGGER.debug("Received message of type %s:\n%s", self.type, self.json(indent=2))

    @property
    def Handler(self):
        msg_class = self.__class__

        class Handler(BaseHandler):
            """Handler for message."""

            async def handle(self, context, responder):
                """Handle the message."""
                return await msg_class.handle(context.message, context, responder)

        return Handler
