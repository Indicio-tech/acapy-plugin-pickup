"""Status Request and response tests"""

from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo
import pytest

import logging

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_status_request_empty_queue(echo: EchoClient, connection: ConnectionInfo):
    """Testing the Status Request Message with no queued messages."""

    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/status-request",
            "~transport": {"return_route": "all"},
        },
    )
    status = await echo.get_message(connection)
    assert status["@type"] == "https://didcomm.org/messagepickup/2.0/status"


@pytest.mark.asyncio
async def test_status_request_with_queue(echo: EchoClient, connection: ConnectionInfo):

    for _ in range(2):
        await echo.send_message(
            connection,
            {
                "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
                "response_resquested": True,
            },
        )

    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/status-request",
            "~transport": {"return_route": "all"},
        },
    )
    status = await echo.get_message(connection)
    assert status["@type"] == "https://didcomm.org/messagepickup/2.0/status"
    assert status["message_count"] == 2


@pytest.mark.asyncio
async def test_recipient_key(echo: EchoClient, connection: ConnectionInfo):
    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/status-request",
            "~transport": {"return_route": "all"},
            "recipient_key": "12345678987654321",
        },
    )
    status = await echo.get_message(connection)
    assert status["@type"] == "https://didcomm.org/messagepickup/2.0/status"
    assert status["recipient_key"] == "12345678987654321"
