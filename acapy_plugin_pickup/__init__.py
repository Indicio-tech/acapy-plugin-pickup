"""ACA-Py Pickup Protocol Plugin."""

from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.core.protocol_registry import ProtocolRegistry
from .protocol import LiveDeliveryChange, MessagesReceived, Status, StatusRequest, DeliveryRequest


async def setup(context: InjectionContext):
    """Setup plugin."""
    protocol_registry = context.inject(ProtocolRegistry)
    assert protocol_registry
    protocol_registry.register_message_types(
        {
            Status.message_type: Status,
            StatusRequest.message_type: StatusRequest,
            DeliveryRequest.message_type: DeliveryRequest,
            MessagesReceived.message_type: MessagesReceived,
            LiveDeliveryChange.message_type: LiveDeliveryChange,
        }
    )
