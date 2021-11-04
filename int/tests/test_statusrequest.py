"""Status Request and response tests"""

import asyncio
from echo_agent.client import EchoClient
import pytest
from acapy_client import Client

import logging
LOGGER = logging.getLogger(__name__)

@pytest.mark.asyncio
def test_statusrequest():

    assert True


@pytest.mark.asyncio
async def test_send(
    connection_id: str, echo: EchoClient
):
    """Test send message"""
    await echo.send_message(
        {
            "@type": "https://github.com/hyperledger/aries-toolbox/tree/master/docs/admin-basicmessage/0.1/send",
            "connection_id": connection_id,
            "content": "Your hovercraft is full of eels.",
        }
    )
    [sent_message, recip_message] = await echo.get_messages()
    assert (
        sent_message["@type"]
        == "https://github.com/hyperledger/aries-toolbox/tree/master/docs/admin-basicmessage/0.1/sent"
    )
    assert (
        recip_message["@type"]
        == "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/basicmessage/1.0/message"
    )
    assert recip_message["content"] == "Your hovercraft is full of eels."
