"""ACA-Py Pickup Protocol Plugin."""

from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.core.protocol_registry import ProtocolRegistry


async def setup(context: InjectionContext):
    """Setup plugin."""
    protocol_registry: ProtocolRegistry = context.inject(ProtocolRegistry)
    assert protocol_registry
    protocol_registry.register_message_types({})
