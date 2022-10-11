"""Status Request and response tests"""

import logging
import asyncio

import pytest
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_status_request_empty_queue(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):
    """Testing the Status Request Message with no queued messages."""

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/status-request",
                "~transport": {"return_route": "all"},
            },
        )
        await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )


@pytest.mark.asyncio
async def test_status_request_with_queue(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):
    await echo.get_messages(connection)

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/status-request",
                "~transport": {"return_route": "all"},
            },
        )
        count_msg = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    initial_count = count_msg["message_count"]

    for _ in range(2):
        await echo.send_message(
            connection,
            {
                "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
                "response_resquested": True,
            },
        )
    await asyncio.sleep(1)

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/status-request",
                "~transport": {"return_route": "all"},
            },
        )
        status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    assert status["message_count"] == initial_count + 2


@pytest.mark.asyncio
async def test_recipient_key(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):
    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/status-request",
                "~transport": {"return_route": "all"},
                "recipient_key": "12345678987654321",
            },
        )
        status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    assert status["recipient_key"] == "12345678987654321"
