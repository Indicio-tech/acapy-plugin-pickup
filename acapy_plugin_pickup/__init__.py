"""ACA-Py Pickup Protocol Plugin."""

import logging
import re
import aioredis
from typing import Dict, Any
import copy

from acapy_plugin_pickup.protocol.delivery import RedisPersistedQueue

from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.core.event_bus import Event, EventBus
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.core.protocol_registry import ProtocolRegistry
from aries_cloudagent.transport.outbound.message import OutboundMessage

from .protocol.delivery import Delivery, DeliveryRequest, MessagesReceived
from .protocol.live_mode import LiveDeliveryChange
from .protocol.status import Status, StatusRequest

UNDELIVERABLE_EVENT_TOPIC = re.compile("acapy::outbound-message::undeliverable")
LOGGER = logging.getLogger(__name__)


async def setup(context: InjectionContext):
    LOGGER.debug("Hit Pickup Plugin setup")
    """Setup plugin."""
    protocol_registry = context.inject(ProtocolRegistry)
    assert protocol_registry
    protocol_registry.register_message_types(
        {
            Status.message_type: Status,
            StatusRequest.message_type: StatusRequest,
            Delivery.message_type: Delivery,
            DeliveryRequest.message_type: DeliveryRequest,
            MessagesReceived.message_type: MessagesReceived,
            LiveDeliveryChange.message_type: LiveDeliveryChange,
        }
    )

    event_bus = context.inject(EventBus)
    event_bus.subscribe(UNDELIVERABLE_EVENT_TOPIC, undeliverable)

    queue = RedisPersistedQueue(redis=await aioredis.from_url("redis://localhost"))
    context.injector.bind_instance(RedisPersistedQueue, queue)


async def undeliverable(profile: Profile, event: Event):
    LOGGER.debug(
        "Undeliverable Event Captured in Pickup Protocol: ", event.topic, event.payload
    )
    queue = profile.inject(RedisPersistedQueue)
    queue.add_message(event.payload)
