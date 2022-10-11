import logging
import asyncio

import pytest
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_delivery_request_empty_queue(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):

    """Testing the Delivery Request with no queued messages."""
    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
                "limit": 1,
                "~transport": {"return_route": "all"},
            },
        )

        await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )


@pytest.mark.asyncio
async def test_delivery_request_with_queued(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
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
    await asyncio.sleep(1)

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
                "limit": 1,
                "~transport": {"return_route": "all"},
            },
        )
        delivery = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/delivery",
        )

    assert len(delivery["~attach"]) == 1


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

        msg = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/delivery",
            timeout=1,
        )
        assert len(msg["~attach"]) == 3
