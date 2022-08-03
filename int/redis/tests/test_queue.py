from os import getenv

from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.transport.outbound.message import OutboundMessage
import pytest
import json
from redis.asyncio import Redis
import time

from acapy_plugin_pickup.undelivered_queue.redis_persisted_queue import (
    RedisPersistedQueue,
    msg_serialize,
)
from acapy_plugin_pickup.undelivered_queue.base import message_id_for_outbound


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
def msg(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload",
        enc_payload="enc_payload",
    )


@pytest.fixture
def msg2(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload2",
        enc_payload="enc_payload2",
    )


@pytest.fixture
def msg3(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload3",
        enc_payload="enc_payload3",
    )


@pytest.fixture
def msg4(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload4",
        enc_payload="enc_payload4",
    )


@pytest.fixture
def another_msg(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="another",
        enc_payload="enc_another",
    )


@pytest.fixture
async def redis():
    host_port = getenv("REDIS", "localhost:6379")
    redis = Redis.from_url(f"redis://{host_port}/test")
    yield redis
    await redis.flushall(asynchronous=True)


@pytest.mark.asyncio
async def test_persistedqueue(
    redis: Redis,
    msg: OutboundMessage,
    another_msg: OutboundMessage,
    msg2: OutboundMessage,
    msg3: OutboundMessage,
    msg4: OutboundMessage,
):
    """
    PersistedQueue Test.
    Unit test for the delivery protocol RedisPersistedQueue class.
    """
    queue = RedisPersistedQueue(redis=redis, ttl_seconds=5)
    key = " ".join(msg.target.recipient_keys)

    # Testing adding a message to the queue.
    assert await queue.message_count_for_key(key) == 0

    await queue.add_message(msg)
    assert await queue.message_count_for_key(key) == 1

    # Testing checking for queued messages.
    assert await queue.has_message_for_key(key)

    # Testing returning and removing a specific message by key.
    msg_from_queue = await queue.get_messages_for_key(key, 1)
    assert isinstance(msg_from_queue[0], OutboundMessage)
    assert msg_serialize(msg_from_queue[0]) == msg_serialize(msg)

    # Check that message removal works, clear the queue
    await queue.remove_messages_for_key(key, [msg])
    assert await queue.message_count_for_key(key) == 0

    # Testing expiration of messages, along with the above message removal
    # method in the case that no messages are present.
    await queue.add_message(msg=msg)

    assert await queue.message_count_for_key(key) == 1

    time.sleep(5)
    assert await queue.message_count_for_key(key) == 0
    assert await queue.get_messages_for_key(key, 1) == []

    # Now we do it again, with multiple messages of different
    # expiration times.
    await queue.add_message(msg=msg)
    assert await queue.message_count_for_key(key) == 1

    time.sleep(1)
    await queue.add_message(msg=msg2)
    assert await queue.message_count_for_key(key) == 2

    time.sleep(1)
    await queue.add_message(msg=msg3)
    assert await queue.message_count_for_key(key) == 3

    time.sleep(1)
    await queue.add_message(msg=msg4)
    assert await queue.message_count_for_key(key) == 4

    time.sleep(2)
    assert await queue.message_count_for_key(key) == 3
    time.sleep(1)
    assert await queue.message_count_for_key(key) == 2
    time.sleep(1)
    assert await queue.message_count_for_key(key) == 1
    time.sleep(1)
    assert await queue.message_count_for_key(key) == 0
    assert await queue.get_messages_for_key(key, 1) == []

    # Testing returning all messages for a key.
    await queue.add_message(msg)
    await queue.add_message(another_msg)
    assert await queue.message_count_for_key(key) == 2
    inspect_messages = await queue.inspect_all_messages_for_key(key)
    assert inspect_messages
    assert len(inspect_messages) == 2
    assert [msg_serialize(msg), msg_serialize(another_msg)] == [
        msg_serialize(msg) for msg in inspect_messages
    ]

    # Testing removing a specific message foe key
    await queue.remove_messages_for_key(key, [msg])
    assert await queue.message_count_for_key(key) == 1
    assert [msg_serialize(another_msg)] == [
        msg_serialize(msg) for msg in await queue.inspect_all_messages_for_key(key)
    ]

    # We've removed this capability, so I don't think we need this test anymore

    # Testing flushing all messages from the queue.
    # assert await queue.flush_messages(key)
    # assert not await queue.inspect_all_messages_for_key(key)
