import json
from typing import Any, Dict, List, Optional
from unittest import mock

import pytest
from acapy_plugin_pickup.undelivered_queue.redis_persisted_queue import (
    RedisPersistedQueue,
    msg_serialize,
)
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
        enc_payload="the_cooler_payload",
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
    msg: OutboundMessage,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(mock_redis, "zadd", CoroutineMock())
    monkeypatch.setattr(mock_redis, "expire", CoroutineMock())
    monkeypatch.setattr(mock_redis, "setex", CoroutineMock())
    await queue.add_message(msg)
    mock_redis.zadd.assert_called_once()
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
    monkeypatch.setattr(mock_redis, "zrange", CoroutineMock(return_value=lindex_ret))
    assert await queue.has_message_for_key(key) == expected
    mock_redis.zrange.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("msg_queue", "messages", "expected"),
    [
        ([], {}, None),
        (
            ["asdf"],
            {"asdf": OutboundMessage(payload="asdf", connection_id="conn_id")},
            OutboundMessage(payload="asdf", connection_id="conn_id"),
        ),
        (
            ["1", "2"],
            {
                "1": OutboundMessage(payload="1", connection_id="conn_id1"),
                "2": OutboundMessage(payload="2", connection_id="conn_id2"),
            },
            OutboundMessage(payload="1", connection_id="conn_id1"),
        ),
        (
            ["1", "2", "3"],
            {
                "1": None,
                "2": None,
                "3": OutboundMessage(payload="3", connection_id="conn_id3"),
            },
            OutboundMessage(payload="3", connection_id="conn_id3"),
        ),
    ],
)
async def test_get_messages_for_key(
    queue: RedisPersistedQueue,
    key: str,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg_queue: List[OutboundMessage],
    messages: Dict[str, OutboundMessage],
    expected: Optional[OutboundMessage],
):
    async def _zrem(key: str, msg_idents):
        if key not in messages or messages[key] is None:
            return None
        for member in msg_idents:
            if member in messages[key]:
                del member

    async def _mget(key: str):

        return [
            json.dumps(msg_serialize(message))
            for message in messages.values()
            if message is not None
        ]

    monkeypatch.setattr(mock_redis, "zrange", CoroutineMock(return_value=msg_queue))
    monkeypatch.setattr(mock_redis, "mget", _mget)
    monkeypatch.setattr(mock_redis, "zrem", _zrem)

    msg = await queue.get_messages_for_key(key, 0)
    if expected is None:
        assert msg == []
    else:
        assert msg
        assert msg_serialize(expected) == msg_serialize(msg[0])


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

    monkeypatch.setattr(mock_redis, "zrange", CoroutineMock(return_value=msg_queue))
    monkeypatch.setattr(mock_redis, "mget", _mget)

    msgs = await queue.inspect_all_messages_for_key(key)
    assert len(msgs) == len(expected)
    for i in range(len(expected)):
        assert msg_serialize(msgs[i]) == msg_serialize(expected[i])


@pytest.mark.asyncio
async def test_remove_messages_for_key(
    queue: RedisPersistedQueue,
    key: str,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg: OutboundMessage,
):
    async def _zrem(key: str, msg_idents):
        if key not in messages or messages[key] is None:
            return None
        for member in msg_idents:
            if member in messages[key]:
                del member

    monkeypatch.setattr(mock_redis, "zrem", _zrem)
    del_mock = CoroutineMock()
    monkeypatch.setattr(mock_redis, "delete", del_mock)

    await queue.remove_messages_for_key(key, [msg])
    del_mock.assert_called_once()
