from unittest.mock import patch

from acapy_plugin_pickup.protocol.delivery import PersistedQueue
from aries_cloudagent.transport.outbound.message import OutboundMessage
import mock
import pytest


@pytest.mark.asyncio
async def test_persistedqueue():
    PQ = await PersistedQueue
    with patch(OutboundMessage) as outboundmsg:
        await PQ.add_message(outboundmsg)
        