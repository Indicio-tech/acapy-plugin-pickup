import logging
import re

from aries_cloudagent.core.event_bus import Event, EventBus
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.core.protocol_registry import ProtocolRegistry

LOGGER = logging.getLogger(__name__)

WEBHOOK_TOPIC = "acapy::webhook::questionanswer"


def register_events(event_bus: EventBus):
    """Register to handle events."""
    event_bus.subscribe(
        re.compile("^acapy::core::startup"),
        on_startup,
    )


async def on_startup(profile: Profile, event: Event):
    """Perform startup actions."""
    protocol_registry = profile.inject(ProtocolRegistry)
    LOGGER.debug("Registered protocols: %s", protocol_registry.message_types)
