from typing import Any, Dict, List, Optional
import pytest
from asynctest import mock
from asynctest.mock import CoroutineMock
from redis.asyncio import Redis

from acapy_plugin_pickup.protocol.delivery import RedisPersistedQueue, msg_serialize
from aries_cloudagent.transport.outbound.message import OutboundMessage
from aries_cloudagent.connections.models.connection_target import ConnectionTarget


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
def mock_redis():
    yield mock.MagicMock(spec=Redis)


@pytest.fixture
def queue(mock_redis):
    yield RedisPersistedQueue(redis=mock_redis)


@pytest.fixture
def key(msg):
    yield ",".join(msg.target.recipient_keys)


@pytest.mark.asyncio
async def test_add_message(
    queue: RedisPersistedQueue,
    key: str,
    msg: OutboundMessage,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(mock_redis, "rpush", CoroutineMock())
    monkeypatch.setattr(mock_redis, "expire", CoroutineMock())
    monkeypatch.setattr(mock_redis, "setex", CoroutineMock())
    await queue.add_message(key, msg)
    assert len(mock_redis.rpush.calls) == 1
    assert len(mock_redis.expire.calls) == 1
    assert len(mock_redis.setex.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("lindex_ret", "expected"), [(None, False), (1, True)])
async def test_has_message_for_key(
    queue: RedisPersistedQueue,
    key: str,
    mock_redis: mock.MagicMock,
    lindex_ret: Any,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(mock_redis, "lindex", CoroutineMock(return_value=lindex_ret))
    assert await queue.has_message_for_key(key) == expected
    assert len(mock_redis.lindex.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("msg_queue", "messages", "expected"),
    [
        ([], {}, None),
        (
            ["asdf"],
            {"asdf": OutboundMessage(payload="asdf")},
            OutboundMessage(payload="asdf"),
        ),
        (
            ["1", "2"],
            {"1": OutboundMessage(payload="1"), "2": OutboundMessage(payload="2")},
            OutboundMessage(payload="1"),
        ),
        (
            [None, None, None, "1"],
            {"1": OutboundMessage(payload="1")},
            OutboundMessage(payload="1"),
        ),
    ],
)
async def test_get_one_message_for_key(
    queue: RedisPersistedQueue,
    key: str,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg_queue: List[OutboundMessage],
    messages: Dict[str, OutboundMessage],
    expected: Optional[OutboundMessage],
):
    def _message_gen():
        yield from msg_queue

    generator = _message_gen()

    async def _lpop(*args, **kwargs):
        try:
            return msg_serialize(next(generator))
        except StopIteration:
            return None

    async def _get(key: str):
        return messages[key]

    monkeypatch.setattr(mock_redis, "lpop", _lpop)
    monkeypatch.setattr(mock_redis, "get", _get)
    monkeypatch.setattr(mock_redis, "delete", CoroutineMock())
    assert (
        msg_serialize(expected) if expected else None
    ) == await queue.get_one_message_for_key(key)


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
