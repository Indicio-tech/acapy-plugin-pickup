import json
from typing import Any, Dict, List, Optional
from unittest import mock

import pytest
from acapy_plugin_pickup.protocol.delivery import RedisPersistedQueue, msg_serialize
from aries_cloudagent.connections.models.connection_target import ConnectionTarget
from aries_cloudagent.transport.outbound.message import OutboundMessage
from pyexpat.errors import messages
from redis.asyncio import Redis


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


class CoroutineMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


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
    mock_redis.rpush.assert_called_once()
    mock_redis.expire.assert_called_once()
    mock_redis.setex.assert_called_once()


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
    mock_redis.lindex.assert_called_once()


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
            ["1", "2", "3"],
            {"1": None, "2": None, "3": OutboundMessage(payload="3")},
            OutboundMessage(payload="3"),
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
            return next(generator)
        except StopIteration:
            return None

    async def _get(key: str):
        if key not in messages or messages[key] is None:
            return None
        return json.dumps(msg_serialize(messages[key]))

    monkeypatch.setattr(mock_redis, "lpop", _lpop)
    monkeypatch.setattr(mock_redis, "get", _get)
    monkeypatch.setattr(mock_redis, "delete", CoroutineMock())
    msg = await queue.get_one_message_for_key(key)
    if expected is None:
        assert expected == msg
    else:
        assert msg
        assert msg_serialize(expected) == msg_serialize(msg)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("msg_queue", "messages", "expected"),
    [
        ([], {}, []),
        (
            ["1", "2", "3"],
            {
                "1": OutboundMessage(payload="1"),
                "2": OutboundMessage(payload="2"),
                "3": OutboundMessage(payload="3"),
            },
            [
                OutboundMessage(payload="1"),
                OutboundMessage(payload="2"),
                OutboundMessage(payload="3"),
            ],
        ),
    ],
)
async def test_inspect_all_messages_for_key(
    queue: RedisPersistedQueue,
    key: str,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg_queue: List[OutboundMessage],
    messages: Dict[str, OutboundMessage],
    expected: List[OutboundMessage],
):
    async def _mget(key: str):
        return [json.dumps(msg_serialize(message)) for message in messages.values()]

    monkeypatch.setattr(mock_redis, "lrange", CoroutineMock(return_value=msg_queue))
    monkeypatch.setattr(mock_redis, "mget", _mget)

    msgs = await queue.inspect_all_messages_for_key(key)
    assert len(msgs) == len(expected)
    for i in range(len(expected)):
        assert msg_serialize(msgs[i]) == msg_serialize(expected[i])


@pytest.mark.asyncio
async def test_remove_message_for_key(
    queue: RedisPersistedQueue,
    key: str,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg: OutboundMessage,
):
    async def _lrem(key: str, count: int, msg_key):
        if key not in messages or messages[key] is None:
            return None
        messages_left = count
        while messages_left != 0:
            for message in messages[key]:
                if msg_key in message:
                    messages[key].pop(message)
            messages_left -= 1
        return count

    monkeypatch.setattr(mock_redis, "lrem", _lrem)
    del_mock = CoroutineMock()
    monkeypatch.setattr(mock_redis, "delete", del_mock)
    monkeypatch.setattr(mock_redis, "lrange", CoroutineMock())

    await queue.remove_message_for_key(key, msg)
    del_mock.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("msg_queue", "message_list"),
    [
        (
            ["1", "2", "3"],
            [
                OutboundMessage(payload="1"),
                OutboundMessage(payload="2"),
                OutboundMessage(payload="3"),
            ],
        ),
    ],
)
async def test_flush_messages(
    queue: RedisPersistedQueue,
    key: str,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg_queue: List[OutboundMessage],
    message_list: List[OutboundMessage],
):
    monkeypatch.setattr(
        RedisPersistedQueue,
        "inspect_all_messages_for_key",
        CoroutineMock(return_value=message_list),
    )
    monkeypatch.setattr(mock_redis, "lrange", CoroutineMock(return_value=msg_queue))
    del_mock = CoroutineMock()
    monkeypatch.setattr(mock_redis, "delete", del_mock)

    flushed = await queue.flush_messages(key)

    assert flushed == message_list
    del_mock.assert_called_once_with(*msg_queue, key)
