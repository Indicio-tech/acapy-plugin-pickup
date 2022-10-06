from typing import Any, Dict, List, Optional
from unittest import mock

import pytest
from acapy_plugin_pickup.undelivered_queue.redis import (
    RedisUndeliveredQueue,
)
from redis.asyncio import Redis


@pytest.fixture
def msg():
    yield b"test message"


@pytest.fixture
def mock_redis():
    yield mock.MagicMock(spec=Redis)


@pytest.fixture
def queue(mock_redis):
    yield RedisUndeliveredQueue(redis=mock_redis)


@pytest.fixture
def key():
    yield "test key"


class CoroutineMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


@pytest.mark.asyncio
async def test_add_message(
    queue: RedisUndeliveredQueue,
    key: str,
    msg: bytes,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(mock_redis, "zadd", CoroutineMock())
    monkeypatch.setattr(mock_redis, "expire", CoroutineMock())
    monkeypatch.setattr(mock_redis, "setex", CoroutineMock())
    await queue.add_message(key, msg)
    mock_redis.zadd.assert_called_once()
    mock_redis.expire.assert_called_once()
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(("lindex_ret", "expected"), [(0, False), (1, True)])
async def test_has_message_for_key(
    queue: RedisUndeliveredQueue,
    key: str,
    mock_redis: mock.MagicMock,
    lindex_ret: Any,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(mock_redis, "zcard", CoroutineMock(return_value=lindex_ret))
    monkeypatch.setattr(queue, "_expire_helper", CoroutineMock())
    assert await queue.has_message_for_key(key) == expected
    mock_redis.zcard.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("msg_queue", "messages", "expected"),
    [
        ([], {}, None),
        (
            ["asdf"],
            {"asdf": b"qwerty"},
            b"qwerty",
        ),
        (
            ["1", "2"],
            {
                "1": b"enc_1",
                "2": b"enc_2",
            },
            b"enc_1",
        ),
        (
            ["1", "2", "3"],
            {
                "1": None,
                "2": None,
                "3": b"enc_3",
            },
            b"enc_3",
        ),
    ],
)
async def test_get_messages_for_key(
    queue: RedisUndeliveredQueue,
    key: str,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg_queue: List[bytes],
    messages: Dict[str, bytes],
    expected: Optional[bytes],
):
    async def _zrem(key: str, *msg_idents):
        if key not in messages or messages[key] is None:
            return None
        for member in msg_idents:
            if member in messages[key]:
                del member

    async def _mget(key: str):

        return [message for message in messages.values() if message is not None]

    monkeypatch.setattr(mock_redis, "zrange", CoroutineMock(return_value=msg_queue))
    monkeypatch.setattr(mock_redis, "mget", _mget)
    monkeypatch.setattr(mock_redis, "zrem", _zrem)

    msg = await queue.get_messages_for_key(key, 0)
    if expected is None:
        assert msg == []
    else:
        assert msg
        assert expected == msg[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("msg_queue", "messages"),
    [
        ([], {}),
        (
            [b"1", b"2", b"3"],
            {
                b"1": b"enc_1",
                b"2": b"enc_2",
                b"3": b"enc_3",
            },
        ),
    ],
)
async def test_remove_messages_for_key(
    queue: RedisUndeliveredQueue,
    key: str,
    msg_queue: list,
    messages: Dict[bytes, bytes],
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    async def _zrem(key: str, *msg_idents):
        if key not in messages or messages[key] is None:
            return None
        for member in msg_idents:
            if member in messages[key]:
                del member

    async def _mget(key: str):

        return [message for message in messages.values() if message is not None]

    monkeypatch.setattr(mock_redis, "mget", _mget)
    monkeypatch.setattr(mock_redis, "zrem", _zrem)
    monkeypatch.setattr(queue, "_expire_helper", CoroutineMock())
    del_mock = CoroutineMock()
    monkeypatch.setattr(mock_redis, "zrange", CoroutineMock(return_value=msg_queue))
    monkeypatch.setattr(mock_redis, "delete", del_mock)

    await queue.remove_messages_for_key(key, messages.keys())
    if msg_queue == []:
        del_mock.assert_not_called()
    else:
        del_mock.assert_called()
