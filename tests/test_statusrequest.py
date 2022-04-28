from unittest.mock import patch

import pytest
from acapy_plugin_pickup.protocol.status import StatusRequest
from aries_cloudagent.messaging.agent_message import AgentMessage
from asynctest import mock
from acapy_plugin_pickup.acapy.message import Transport


@pytest.mark.asyncio
async def test_status_request(context, mock_responder):
    """ """
    handler = StatusRequest()

    handler.transport = mock.MagicMock(spec=Transport)
    handler.transport.return_route = "all"

    with patch.object(mock_responder, "send_reply", mock.CoroutineMock()), patch.object(
        AgentMessage, "assign_thread_from", mock.CoroutineMock()
    ):

        # mock_return_route.return_value = "all"

        await handler.handle(context, mock_responder)
