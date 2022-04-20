import aioredis

from acapy_plugin_pickup.protocol.delivery import PersistedQueue
from aries_cloudagent.transport.outbound.message import OutboundMessage
import pytest


@pytest.fixture
def target():
    yield {
        "did":"some_did",
        "endpoint":"some_endpoint",
        "label":"some_label",
        "recipient_keys":"recipient_keys",
        "routing_keys":"routing_keys",
        "sender_key":"some_sender_key"
        }

@pytest.fixture
def msg(target):
    yield OutboundMessage(
        connection_id="conn_id", 
        target=target,
        reply_from_verkey="reply_from_verkey",
        payload="payload"
        )

@pytest.mark.asyncio
async def test_persistedqueue(msg):
    """
    PersistedQueue Test.

    Unit test for the PersistedQueue class in 
    """
    PQ = PersistedQueue(redis = await aioredis.from_url("redis://localhost/1"))
    key = msg.target["recipient_keys"]

    await PQ.queue_by_key.flushdb(key)
    initial_queue = await PQ.queue_by_key.llen(key)

    await PQ.add_message(key, str(msg))
    added_queue = await PQ.queue_by_key.llen(key)
    assert added_queue == initial_queue + 1

    message_for_key = await PQ.has_message_for_key(key)
    assert message_for_key

    message_count = await PQ.message_count_for_key(key)
    assert message_count == await PQ.queue_by_key.llen(key)

    get_message_for_key = await PQ.get_one_message_for_key(key)
    assert str(get_message_for_key) == str(msg)
    assert await PQ.queue_by_key.llen(key) == 0

    await PQ.add_message(key, str(msg))
    await PQ.add_message(key, str(msg))
    new_added_queue_len = await PQ.queue_by_key.llen(key)
    inspect_messages = await PQ.inspect_all_messages_for_key(key)
    assert inspect_messages
    assert len(inspect_messages) == new_added_queue_len

    remove_message = await PQ.remove_message_for_key(key)
    assert remove_message
    assert await PQ.queue_by_key.llen(key) == 1
