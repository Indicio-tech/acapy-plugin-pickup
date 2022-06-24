from os import getenv

from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.transport.outbound.message import OutboundMessage
import pytest
from redis.asyncio import Redis

from acapy_plugin_pickup.protocol.delivery import RedisPersistedQueue, msg_serialize


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


@pytest.fixture
def another_msg(target):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="another",
    )


@pytest.fixture
async def redis():
    host_port = getenv("REDIS", "localhost:6379")
    redis = Redis.from_url(f"redis://{host_port}/test")
    yield redis
    await redis.flushall(asynchronous=True)


@pytest.mark.asyncio
async def test_persistedqueue(
    redis: Redis, msg: OutboundMessage, another_msg: OutboundMessage
):
    """
    PersistedQueue Test.
    Unit test for the delivery protocol RedisPersistedQueue class.
    """
    queue = RedisPersistedQueue(redis=redis)
    key = " ".join(msg.target.recipient_keys)

    assert await queue.message_count_for_key(key) == 0

    await queue.add_message(key, msg)
    assert await queue.message_count_for_key(key) == 1

    assert await queue.has_message_for_key(key)

    msg_from_queue = await queue.get_one_message_for_key(key)
    assert isinstance(msg_from_queue, OutboundMessage)
    assert msg_serialize(msg_from_queue) == msg_serialize(msg)

    assert await queue.message_count_for_key(key) == 0

    await queue.add_message(key, msg)
    await queue.add_message(key, another_msg)
    assert await queue.message_count_for_key(key) == 2
    inspect_messages = await queue.inspect_all_messages_for_key(key)
    assert inspect_messages
    assert len(inspect_messages) == 2
    assert [msg_serialize(msg), msg_serialize(another_msg)] == [
        msg_serialize(msg) for msg in inspect_messages
    ]

    await queue.remove_message_for_key(key, msg)
    assert await queue.message_count_for_key(key) == 1
    assert [msg_serialize(another_msg)] == [
        msg_serialize(msg) for msg in await queue.inspect_all_messages_for_key(key)
    ]

    assert await queue.flush_messages(key)
    assert not await queue.inspect_all_messages_for_key(key)
