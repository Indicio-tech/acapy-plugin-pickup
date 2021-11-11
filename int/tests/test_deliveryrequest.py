import re
from attr import resolve_types
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
            "~transport": {
                "return_route": "all"
            }
        }
    )

    status = await echo.get_message(connection)
    assert (
        status["@type"]
        == "https://didcomm.org/messagepickup/2.0/status"
    )


@pytest.mark.asyncio
async def test_delivery_request_with_queued(
    echo: EchoClient, connection: ConnectionInfo
):
    await echo.send_message(
        connection,
        {
            "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
                "response_resquested": True
        }
    )

    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
            "limit": 1,
            "~transport": {
                "return_route": "all"
            }
        }
    )

    response = await echo.get_message(connection)
    assert (
        response["@type"]
        == "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping_response"
    )

