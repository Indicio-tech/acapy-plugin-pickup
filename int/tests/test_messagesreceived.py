from echo_agent.client import EchoClient
from echo_agent.client import ConnectionInfo
import pytest

@pytest.mark.asyncio
async def test_messages_received(
    echo: EchoClient, connection: ConnectionInfo
):
    assert True