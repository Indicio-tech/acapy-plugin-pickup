from os import getenv

from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.transport.outbound.message import OutboundMessage
import pytest
import json
from hashlib import sha256
from redis.asyncio import Redis
import time

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
def msg2(target):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload2",
    )


@pytest.fixture
def msg3(target):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload3",
    )


@pytest.fixture
def msg4(target):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload4",
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
    queue = RedisPersistedQueue(redis=redis)
    key = " ".join(msg.target.recipient_keys)

    # Testing adding a message to the queue.
    assert await queue.message_count_for_key(key) == 0

    await queue.add_message(key, msg)
    assert await queue.message_count_for_key(key) == 1

    # Testing checking for queued messages.
    assert await queue.has_message_for_key(key)

    # Testing returning and removing a specific message by key.
    msg_from_queue = await queue.get_one_message_for_key(key)
    assert isinstance(msg_from_queue, OutboundMessage)
    assert msg_serialize(msg_from_queue) == msg_serialize(msg)

    assert await queue.message_count_for_key(key) == 0

    # Testing expiration of messages, along with the above message removal
    # method in the case that no messages are present.
    msg_key = sha256(
        msg.payload.encode("utf-8") if isinstance(msg.payload, str) else msg.payload
    ).digest()
    await queue.queue_by_key.rpush(key, msg_key)
    await queue.queue_by_key.setex(
        msg_key,
        5,  # New message will expire in 5 seconds
        json.dumps(msg_serialize(msg)),
    )

    assert await queue.message_count_for_key(key) == 1

    time.sleep(5)
    assert await queue.message_count_for_key(key) == 0
    assert await queue.get_one_message_for_key(key) == None

    # Now we do it again, with multiple messages of different
    # expiration times.
    msg_key = sha256(
        msg.payload.encode("utf-8") if isinstance(msg.payload, str) else msg.payload
    ).digest()
    await queue.queue_by_key.rpush(key, msg_key)
    await queue.queue_by_key.setex(msg_key, 1, json.dumps(msg_serialize(msg)))
    assert await queue.message_count_for_key(key) == 1

    msg2_key = sha256(
        msg2.payload.encode("utf-8") if isinstance(msg2.payload, str) else msg2.payload
    ).digest()
    await queue.queue_by_key.rpush(key, msg2_key)
    await queue.queue_by_key.setex(msg2_key, 2, json.dumps(msg_serialize(msg2)))
    assert await queue.message_count_for_key(key) == 2

    msg3_key = sha256(
        msg3.payload.encode("utf-8") if isinstance(msg3.payload, str) else msg3.payload
    ).digest()
    await queue.queue_by_key.rpush(key, msg3_key)
    await queue.queue_by_key.setex(msg3_key, 3, json.dumps(msg_serialize(msg3)))
    assert await queue.message_count_for_key(key) == 3

    msg4_key = sha256(
        msg4.payload.encode("utf-8") if isinstance(msg4.payload, str) else msg4.payload
    ).digest()
    await queue.queue_by_key.rpush(key, msg4_key)
    await queue.queue_by_key.setex(msg4_key, 4, json.dumps(msg_serialize(msg4)))
    assert await queue.message_count_for_key(key) == 4

    time.sleep(1)
    assert await queue.message_count_for_key(key) == 3
    time.sleep(1)
    assert await queue.message_count_for_key(key) == 2
    time.sleep(1)
    assert await queue.message_count_for_key(key) == 1
    time.sleep(1)
    assert await queue.message_count_for_key(key) == 0
    assert await queue.get_one_message_for_key(key) == None

    # Testing returning all messages for a key.
    await queue.add_message(key, msg)
    await queue.add_message(key, another_msg)
    assert await queue.message_count_for_key(key) == 2
    inspect_messages = await queue.inspect_all_messages_for_key(key)
    assert inspect_messages
    assert len(inspect_messages) == 2
    assert [msg_serialize(msg), msg_serialize(another_msg)] == [
        msg_serialize(msg) for msg in inspect_messages
    ]

    # Testing removing a specific message foe key
    await queue.remove_message_for_key(key, msg)
    assert await queue.message_count_for_key(key) == 1
    assert [msg_serialize(another_msg)] == [
        msg_serialize(msg) for msg in await queue.inspect_all_messages_for_key(key)
    ]

    # Testing flushing all messages from the queue.
    assert await queue.flush_messages(key)
    assert not await queue.inspect_all_messages_for_key(key)
