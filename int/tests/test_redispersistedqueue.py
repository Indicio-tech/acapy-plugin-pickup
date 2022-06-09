import aioredis

from acapy_plugin_pickup.protocol.delivery import RedisPersistedQueue
from aries_cloudagent.transport.outbound.message import OutboundMessage
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo
from acapy_plugin_pickup.protocol.status import Status
import pytest

@pytest.fixture
async def queue():
    return RedisPersistedQueue(redis=await aioredis.from_url("redis://localhost/"))


@pytest.mark.asyncio
async def test_redispersistedqueue_count(
    echo: EchoClient, 
    connection: ConnectionInfo
    ):
    """
    RedisPersistedQueue Test.

    Integration test for the RedisPersistedQueue class in the delivery protocol. 
    """
    
    initial_queue:Status = await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/status-request",
            "~transport": {"return_route": "all"},
        },
    )
    initial_count = initial_queue.message_count

    await echo.send_message(
            connection,
            {
                "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
                "response_resquested": True,
            },
        )

    added_queue:Status = await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/status-request",
            "~transport": {"return_route": "all"},
        },
    )
    added_count = added_queue.message_count
    
    assert added_count == initial_count + 1

@pytest.mark.asyncio
async def test_redispersistedqueue_retrieval(
    msg: OutboundMessage,
    echo: EchoClient, 
    connection: ConnectionInfo,
    queue: RedisPersistedQueue
):

    initial_queue:Status = await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/status-request",
            "~transport": {"return_route": "all"},
        },
    )
    assert initial_queue.message_count == 1

    await echo.send_message(
        connection,
        {
            "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
            "~transport": {"return_route": "all"},
            "limit": 1,
        },
    )


'''
    message_for_key = await queue.has_message_for_key(key)
    assert message_for_key

    message_count = await queue.message_count_for_key(key)
    assert message_count == await queue.queue_by_key.llen(key)

    get_message_for_key = await queue.get_one_message_for_key(key)
    assert str(get_message_for_key) == str(msg)
    assert await queue.queue_by_key.llen(key) == 0

    await queue.add_message(key, str(msg))
    await queue.add_message(key, str(msg))
    new_added_queue_len = await queue.queue_by_key.llen(key)

    inspect_messages = await queue.inspect_all_messages_for_key(key)

    assert inspect_messages
    assert len(inspect_messages) == new_added_queue_len

    remove_message = await queue.remove_message_for_key(key)
    assert remove_message
    assert await queue.queue_by_key.llen(key) == 1
'''
