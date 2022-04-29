import pytest
from aries_cloudagent.connections.models.conn_record import ConnRecord
from aries_cloudagent.core.event_bus import EventBus
from aries_cloudagent.core.in_memory import InMemoryProfile
from aries_cloudagent.core.protocol_registry import ProtocolRegistry
from aries_cloudagent.messaging.request_context import RequestContext
from aries_cloudagent.messaging.responder import BaseResponder, MockResponder
from asynctest import mock
from aries_cloudagent.transport.inbound.delivery_queue import DeliveryQueue
from aries_cloudagent.transport.inbound.manager import InboundTransportManager
from aries_cloudagent.transport.inbound.receipt import MessageReceipt


@pytest.fixture
def mock_admin_connection():
    """Mock connection fixture."""
    connection = mock.MagicMock(spec=ConnRecord)
    connection.metadata_get = mock.CoroutineMock(return_value="admin")
    yield connection


@pytest.fixture
def event_bus():
    """Event bus fixture."""
    yield EventBus()


@pytest.fixture
def mock_responder():
    """Mock responder fixture."""
    yield MockResponder()


@pytest.fixture
def profile(event_bus, mock_responder):
    """Profile fixture."""
    yield InMemoryProfile.test_profile(
        bind={
            EventBus: event_bus,
            BaseResponder: mock_responder,
            ProtocolRegistry: ProtocolRegistry(),
        }
    )


@pytest.fixture
def manager():
    manager = InboundTransportManager()
    manager.undelivered_queue = DeliveryQueue()
    yield manager


@pytest.fixture
def context(profile, mock_admin_connection):
    """RequestContext fixture."""
    context = RequestContext(profile)
    context.connection_record = mock_admin_connection
    context.connection_ready = True
    context.inject = mock.MagicMock(spec=InboundTransportManager)
    context.message_receipt = mock.CoroutineMock(spec=MessageReceipt)
    yield context
