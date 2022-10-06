from os import getenv

import pytest
from redis.asyncio import Redis
import time

from acapy_plugin_pickup.undelivered_queue.redis import (
    RedisUndeliveredQueue,
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
):
    """
    PersistedQueue Test.
    Unit test for the delivery protocol RedisUndeliveredQueue class.
    """
    queue = RedisUndeliveredQueue(redis=redis, ttl_seconds=5)
    key = "key"

    # Testing adding a message to the queue.
    assert await queue.message_count_for_key(key) == 0

    await queue.add_message(key, b"msg")
    assert await queue.message_count_for_key(key) == 1

    # Testing checking for queued messages.
    assert await queue.has_message_for_key(key)

    # Testing returning and removing a specific message by key.
    msg_from_queue = await queue.get_messages_for_key(key, 1)
    assert isinstance(msg_from_queue[0], bytes)
    assert msg_from_queue[0] == b"msg"

    # Check that message removal works, clear the queue
    await queue.remove_messages_for_key(key, [queue.ident_from_message(b"msg")])
    assert await queue.message_count_for_key(key) == 0

    # Testing expiration of messages, along with the above message removal
    # method in the case that no messages are present.
    await queue.add_message(key, b"msg")

    assert await queue.message_count_for_key(key) == 1

    time.sleep(5)
    assert await queue.message_count_for_key(key) == 0
    assert await queue.get_messages_for_key(key, 1) == []

    # Now we do it again, with multiple messages of different
    # expiration times.
    await queue.add_message(key, b"msg")
    assert await queue.message_count_for_key(key) == 1

    time.sleep(1)
    await queue.add_message(key, b"msg2")
    assert await queue.message_count_for_key(key) == 2

    time.sleep(1)
    await queue.add_message(key, b"msg3")
    assert await queue.message_count_for_key(key) == 3

    time.sleep(1)
    await queue.add_message(key, b"msg4")
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
    await queue.add_message(key, b"msg")
    await queue.add_message(key, b"another msg")
    assert await queue.message_count_for_key(key) == 2
    inspect_messages = await queue.message_count_for_key(key)
    assert inspect_messages == 2
    assert [
        b"msg",
        b"another msg",
    ] == [msg for msg in await queue.get_messages_for_key(key, inspect_messages)]

    # Testing removing a specific message foe key
    await queue.remove_messages_for_key(key, [queue.ident_from_message(b"msg")])
    new_count = await queue.message_count_for_key(key)
    assert new_count == 1
    assert [b"another msg"] == [
        msg for msg in await queue.get_messages_for_key(key, new_count)
    ]
