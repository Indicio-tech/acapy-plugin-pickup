"""Plugin setup tests"""

import logging

import pytest
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo

LOGGER = logging.getLogger(__name__)


#TODO: test for registered messages type

@pytest.mark.asyncio
async def test_protocol_message(echo: EchoClient, connection: ConnectionInfo):
    """Testing the registered message types returned from the discovery."""

    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/discover-features/2.0/queries",
            "queries": [
            {
                "feature-type": "protocol",
                "match": "https://didcomm.org/messagepickup/2.0*"
            }
            ],
            "~transport": {"return_route": "all"},
        },
    )
    response = await echo.get_message(connection)
    LOGGER.debug(f"discovery test {response}")
    assert response["disclosures"][0]["id"] == "https://didcomm.org/messagepickup/2.0"
    
#TODO: test registered events
    