import asyncio
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo
import pytest

import logging

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_delivery_request_empty_queue(
    echo: EchoClient, connection: ConnectionInfo
):

    """Testing the Delivery Request with no queued messages."""
    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
            "limit": 1,
            "~transport": {"return_route": "all"},
        },
    )

    status = await echo.get_message(connection)
    assert status["@type"] == "https://didcomm.org/messagepickup/2.0/status"


@pytest.mark.asyncio
async def test_delivery_request_with_queued(
    echo: EchoClient, connection: ConnectionInfo
):
    await echo.send_message(
        connection,
        {
            "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
            "response_resquested": True,
        },
    )

    # One of two things is happening here, and I'm not sure which. Either, we're running into a bug
    # we believe we found earlier, where the first message on startup is not queued, OR the first message
    # is added to the queue too slowly, and our delivery-request message arrives to an empty queue. Either way,
    # sending a second message to the queue solves the problem.
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
            "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
            "limit": 1,
            "~transport": {"return_route": "all"},
        },
    )

    response = await echo.get_message(connection)
    assert response["@type"] == "https://didcomm.org/messagepickup/2.0/delivery"


@pytest.mark.asyncio
async def test_delivery_request_multi_delivery(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):
    for _ in range(3):
        await echo.send_message(
            connection,
            {
                "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
                "response_resquested": True,
            },
        )

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
                "limit": 3,
                "~transport": {"return_route": "all"},
            },
        )

        msg = await echo.get_message(connection, session=session, timeout=1)
        assert msg["@type"] == "https://didcomm.org/messagepickup/2.0/delivery"
        assert len(msg["~attach"]) == 3
