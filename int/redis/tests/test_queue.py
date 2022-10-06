from os import getenv

from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.transport.outbound.message import OutboundMessage
import pytest
import json
from redis.asyncio import Redis
import time

from acapy_plugin_pickup.undelivered_queue.redis import (
    RedisUndeliveredQueue,
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
        enc_payload=bytes(
            json.dumps(
                {
                    "protected": "protected_key",
                    "iv": "test_iv",
                    "ciphertext": "test_ciphertext",
                    "tag": "test_tag",
                }
            ),
            "utf-8",
        ),
    )


@pytest.fixture
def msg2(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload2",
        enc_payload=bytes(
            json.dumps(
                {
                    "protected": "protected_key2",
                    "iv": "test_iv2",
                    "ciphertext": "test_ciphertext2",
                    "tag": "test_tag2",
                }
            ),
            "utf-8",
        ),
    )


@pytest.fixture
def msg3(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload3",
        enc_payload=bytes(
            json.dumps(
                {
                    "protected": "protected_key3",
                    "iv": "test_iv3",
                    "ciphertext": "test_ciphertext3",
                    "tag": "test_tag3",
                }
            ),
            "utf-8",
        ),
    )


@pytest.fixture
def msg4(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="payload4",
        enc_payload=bytes(
            json.dumps(
                {
                    "protected": "protected_key4",
                    "iv": "test_iv4",
                    "ciphertext": "test_ciphertext4",
                    "tag": "test_tag4",
                }
            ),
            "utf-8",
        ),
    )


@pytest.fixture
def another_msg(target: ConnectionTarget):
    yield OutboundMessage(
        connection_id="conn_id",
        target=target,
        target_list=[],
        reply_from_verkey="reply_from_verkey",
        payload="another",
        enc_payload=bytes(
            json.dumps(
                {
                    "protected": "other_protected_key",
                    "iv": "other_test_iv",
                    "ciphertext": "other_test_ciphertext",
                    "tag": "other_test_tag",
                }
            ),
            "utf-8",
        ),
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
    msg: str or bytes,
    another_msg: str or bytes,
    msg2: str or bytes,
    msg3: str or bytes,
    msg4: str or bytes,
):
    """
    PersistedQueue Test.
    Unit test for the delivery protocol RedisUndeliveredQueue class.
    """
    queue = RedisUndeliveredQueue(redis=redis, ttl_seconds=5)
    key = " ".join(msg.target.recipient_keys)

    # Testing adding a message to the queue.
    assert await queue.message_count_for_key(key) == 0

    await queue.add_message(key, msg.enc_payload)
    assert await queue.message_count_for_key(key) == 1

    # Testing checking for queued messages.
    assert await queue.has_message_for_key(key)

    # Testing returning and removing a specific message by key.
    msg_from_queue = await queue.get_messages_for_key(key, 1)
    assert isinstance(msg_from_queue[0], bytes)
    assert msg_from_queue[0] == msg.enc_payload

    # Check that message removal works, clear the queue
    await queue.remove_messages_for_key(key, msg.enc_payload)
    assert await queue.message_count_for_key(key) == 0

    # Testing expiration of messages, along with the above message removal
    # method in the case that no messages are present.
    await queue.add_message(key, msg.enc_payload)

    assert await queue.message_count_for_key(key) == 1

    time.sleep(5)
    assert await queue.message_count_for_key(key) == 0
    assert await queue.get_messages_for_key(key, 1) == []

    # Now we do it again, with multiple messages of different
    # expiration times.
    await queue.add_message(key, msg.enc_payload)
    assert await queue.message_count_for_key(key) == 1

    time.sleep(1)
    await queue.add_message(key, msg2.enc_payload)
    assert await queue.message_count_for_key(key) == 2

    time.sleep(1)
    await queue.add_message(key, msg3.enc_payload)
    assert await queue.message_count_for_key(key) == 3

    time.sleep(1)
    await queue.add_message(key, msg4.enc_payload)
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
    await queue.add_message(key, msg.enc_payload)
    await queue.add_message(key, another_msg.enc_payload)
    assert await queue.message_count_for_key(key) == 2
    inspect_messages = await queue.inspect_all_messages_for_key(key)
    assert inspect_messages
    assert len(inspect_messages) == 2
    assert [
        msg.enc_payload,
        another_msg.enc_payload,
    ] == [msg for msg in inspect_messages]

    # Testing removing a specific message foe key
    await queue.remove_messages_for_key(key, msg.enc_payload)
    assert await queue.message_count_for_key(key) == 1
    assert [another_msg.enc_payload] == [
        msg for msg in await queue.inspect_all_messages_for_key(key)
    ]
