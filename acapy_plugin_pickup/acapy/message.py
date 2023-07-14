"""Simple Agent Message class."""

from abc import ABC
from datetime import datetime
import json
import logging
from typing import Any, ClassVar, Dict, Mapping, Optional, Union
from typing_extensions import Annotated, Literal
from uuid import uuid4
import uuid

from aries_cloudagent.messaging.base_handler import BaseHandler
from aries_cloudagent.messaging.base_message import BaseMessage
from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder
from aries_cloudagent.wallet.util import bytes_to_b64
from pydantic import BaseModel, Field, parse_obj_as
from pydantic.class_validators import validator, root_validator
from pydantic.types import StrictInt

from acapy_plugin_pickup.valid import ISODateTime


LOGGER = logging.getLogger(__name__)


class AttachData(BaseModel):
    class Config:
        allow_population_by_field_name = True

    base64: Annotated[Optional[str], Field(description="Base64-encoded data")] = None
    json_: Annotated[
        Optional[dict], Field(description="JSON-serialized data", alias="json")
    ] = None
    links: Annotated[
        Optional[str], Field(description="List of hypertext links to data")
    ] = None

    @root_validator(pre=True)
    @classmethod
    def _mutual_exclusion_validate(cls, values):
        if len(set(values.keys()) & {"base64", "json", "links", "json_"}) != 1:
            raise ValueError("AttachData: choose exactly one of base64, json, or links")
        return values


class Attach(BaseModel):
    ident: Annotated[str, Field(alias="@id")]
    mime_type: Annotated[str, Field(alias="mime-type")]
    filename: Optional[str] = None
    byte_count: Optional[StrictInt] = None
    lastmod_time: Optional[datetime]
    description: Optional[str]
    data: AttachData

    class Config:
        allow_population_by_field_name = True

    @classmethod
    def data_base64(
        cls,
        value: Union[Mapping, bytes, str],
        *,
        ident: str = None,
        description: str = None,
        filename: str = None,
        lastmod_time: str = None,
        byte_count: int = None,
    ):
        """
        Create `AttachDecorator` instance on base64-encoded data from input mapping.

        Given mapping, JSON dump, base64-encode, and embed
        it as data; mark `application/json` MIME type.

        Args:
            mapping: (dict) data structure; e.g., indy production
            ident: optional attachment identifier (default random UUID4)
            description: optional attachment description
            filename: optional attachment filename
            lastmod_time: optional attachment last modification time
            byte_count: optional attachment byte count

        """
        if isinstance(value, Mapping):
            value = json.dumps(value).encode()
        if isinstance(value, str):
            value = value.encode()

        attach_data = AttachData(base64=bytes_to_b64(value))

        return cls(
            ident=ident or str(uuid.uuid4()),
            description=description,
            filename=filename,
            mime_type="application/json",
            lastmod_time=lastmod_time,
            byte_count=byte_count,
            data=attach_data,
        )


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
            Dict[
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


class Transport(BaseModel):
    """Tranpsport Decorator object."""

    return_route: Literal["none", "all", "thread"] = "none"


class AgentMessage(BaseModel, BaseMessage, ABC):
    """AgentMessage Interface Definition."""

    message_type: ClassVar[str] = ""

    id: Annotated[str, Field(alias="@id", default_factory=lambda: str(uuid4()))]
    type: Annotated[Optional[str], Field(alias="@type")] = None
    thread: Annotated[Optional[Thread], Field(alias="~thread")] = None
    transport: Annotated[Optional[Transport], Field(alias="~transport")] = None

    class Config:
        """AgentMessage Config."""

        json_encoders = {ISODateTime: lambda value: value.isoformat()}

    @validator("type", pre=True, always=True)
    @classmethod
    def _type(cls, value):
        """Set type if not present."""
        if not value:
            return cls.message_type
        if value != cls.message_type:
            raise ValueError(
                "Invalid message type for {}: {}".format(cls.__name__, value)
            )
        return value

    @property
    def _id(self):
        return self.id

    @property
    def _message_type(self):
        """Return the message type for this message."""
        return self.message_type

    @property
    def _thread_id(self) -> Optional[str]:
        """Return this message's thread id."""
        return self.thread and self.thread.thid

    def serialize(self) -> dict:
        """Serialize an instance of message to dictionary."""
        return self.dict(exclude_none=True, by_alias=True)

    @classmethod
    def deserialize(cls, value: Mapping[str, Any]) -> "AgentMessage":
        """Deserialize an instance of message."""
        return parse_obj_as(cls, value)

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

    def json(self, **kwargs):
        """Dump to json."""
        return super().json(exclude_none=True, by_alias=True, **kwargs)

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

    # Fulfill Responder Message Protocol

    def to_json(self) -> str:
        """Dump to json."""
        return self.json()
