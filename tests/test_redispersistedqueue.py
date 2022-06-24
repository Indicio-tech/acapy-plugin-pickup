import pytest
from asynctest import mock
from redis.asyncio import Redis

from acapy_plugin_pickup.protocol.delivery import RedisPersistedQueue
from aries_cloudagent.transport.outbound.message import OutboundMessage
from aries_cloudagent.connections.models.connection_target import ConnectionTarget


"""
{
  "result": {
    "did": "Sfrv1gcBQyqRy2EGfkZDek",
    "verkey": "EzUpTawM8uLQfGW9pTt6HWVT6ZsTeFdgjxSU7WLTRCVm",
    "posture": "wallet_only",
    "key_type": "ed25519",
    "method": "sov"
  }
}
"""


@pytest.fixture
def target():
    yield ConnectionTarget(
        did="Sfrv1gcBQyqRy2EGfkZDek",
        endpoint="some_endpoint",
        label="some_label",
        recipient_keys=["EzUpTawM8uLQfGW9pTt6HWVT6ZsTeFdgjxSU7WLTRCVm"],
        routing_keys=["EzUpTawM8uLQfGW9pTt6HWVT6ZsTeFdgjxSU7WLTRCVm"],
        sender_key="EzUpTawM8uLQfGW9pTt6HWVT6ZsTeFdgjxSU7WLTRCVm",
    )


@pytest.fixture
def msg(target):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload",
    )


@pytest.mark.asyncio
async def test_persistedqueue(msg):
    """
    PersistedQueue Test.
    Unit test for the delivery protocol RedisPersistedQueue class.
    """
    queue = RedisPersistedQueue(redis=mock.MagicMock(spec=Redis))
    key = " ".join(msg.target.recipient_keys)

    initial_queue = await queue.message_count_for_key(key)

    await queue.add_message(key, msg)
    added_queue = await queue.message_count_for_key(key)
    assert added_queue == initial_queue + 1

    message_for_key = await queue.has_message_for_key(key)
    assert message_for_key

    message_count = await queue.message_count_for_key(key)
    assert message_count == await queue.message_count_for_key(key)

    get_message_for_key = await queue.get_one_message_for_key(key)
    assert str(get_message_for_key) == str(msg)
    assert await queue.message_count_for_key(key) == 0

    await queue.add_message(key, msg)
    await queue.add_message(key, msg)
    new_added_queue_len = await queue.message_count_for_key(key)
    inspect_messages = await queue.inspect_all_messages_for_key(key)
    assert inspect_messages
    assert len(inspect_messages) == new_added_queue_len

    remove_message = await queue.remove_message_for_key(key)
    assert remove_message
    assert await queue.message_count_for_key(key) == 1
