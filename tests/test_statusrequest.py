from unittest.mock import patch

import pytest
from acapy_plugin_pickup.acapy.message import Transport
from acapy_plugin_pickup.protocol.status import Status, StatusRequest
from aries_cloudagent.messaging.agent_message import AgentMessage
from asynctest import mock


@pytest.mark.asyncio
async def test_status_request(context, mock_responder):
    """Unit test for status_request"""
    handler = StatusRequest()

    handler.transport = mock.MagicMock(spec=Transport)
    handler.transport.return_route = "all"

    with patch.object(
        mock_responder, "send_reply", mock.CoroutineMock()
    ) as mock_reply:  # , patch.object(
        #     AgentMessage, "assign_thread_from", mock.CoroutineMock()
        # ) as mock_assign_thread:

        await handler.handle(context, mock_responder)

        mock_reply.assert_called_once()
        print(mock_reply.call_args)
        assert False
        # mock_assign_thread.assert_called_once()
