import asyncio
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo
import pytest

import logging
from time import sleep

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

    # This message needs to wait for the queue processing of the EchoClient,
    # or else a Status message is sent in response instead of the expected ping-response
    sleep(2)
    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
            "limit": 1,
            "~transport": {"return_route": "all"},
        },
    )

    response = await echo.get_message(connection)
    assert (
        response["@type"]
        == "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping_response"
    )


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

        for _ in range(3):
            msg = await echo.get_message(connection, session=session, timeout=1)
            assert (
                msg["@type"]
                == "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping_response"
            )
