import pytest
from acapy_plugin_pickup.acapy.message import Transport
from acapy_plugin_pickup.protocol.delivery import MessagesReceived
from asynctest import mock


@pytest.fixture
def message_id_list():
    _message_id_list = ["01234, 56789"]
    yield _message_id_list


@pytest.mark.asyncio
async def test_messagesreceived(context, mock_responder, message_id_list):
    """Unit test for messages_received"""
    handler = MessagesReceived(message_id_list=message_id_list)

    handler.transport = mock.MagicMock(spec=Transport)
    handler.transport.return_route = "all"

    await handler.handle(context, mock_responder)
