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