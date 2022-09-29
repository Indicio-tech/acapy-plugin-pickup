from typing import Any, Dict, List, Optional
from unittest import mock

import pytest
from acapy_plugin_pickup.undelivered_queue.redis_persisted_queue import (
    RedisPersistedQueue,
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
    key: str,
    msg: OutboundMessage,
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(mock_redis, "zadd", CoroutineMock())
    monkeypatch.setattr(mock_redis, "expire", CoroutineMock())
    monkeypatch.setattr(mock_redis, "setex", CoroutineMock())
    await queue.add_message(key, msg.enc_payload)
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
            {
                "asdf": OutboundMessage(
                    payload="asdf", connection_id="conn_id", enc_payload="qwerty"
                ).enc_payload
            },
            OutboundMessage(
                payload="asdf", connection_id="conn_id", enc_payload="qwerty"
            ).enc_payload,
        ),
        (
            ["1", "2"],
            {
                "1": OutboundMessage(
                    payload="1", connection_id="conn_id1", enc_payload="enc_1"
                ).enc_payload,
                "2": OutboundMessage(
                    payload="2", connection_id="conn_id2", enc_payload="enc_2"
                ).enc_payload,
            },
            OutboundMessage(
                payload="1", connection_id="conn_id1", enc_payload="enc_1"
            ).enc_payload,
        ),
        (
            ["1", "2", "3"],
            {
                "1": None,
                "2": None,
                "3": OutboundMessage(
                    payload="3", connection_id="conn_id3", enc_payload="enc_3"
                ).enc_payload,
            },
            OutboundMessage(
                payload="3", connection_id="conn_id3", enc_payload="enc_3"
            ).enc_payload,
        ),
    ],
)
async def test_get_messages_for_key(
    queue: RedisPersistedQueue,
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
    ("msg_queue", "messages", "expected"),
    [
        ([], {}, []),
        (
            ["1", "2", "3"],
            {
                "1": OutboundMessage(payload="1", enc_payload="enc_1").enc_payload,
                "2": OutboundMessage(payload="2", enc_payload="enc_2").enc_payload,
                "3": OutboundMessage(payload="3", enc_payload="enc_3").enc_payload,
            },
            [
                OutboundMessage(payload="1", enc_payload="enc_1").enc_payload,
                OutboundMessage(payload="2", enc_payload="enc_2").enc_payload,
                OutboundMessage(payload="3", enc_payload="enc_3").enc_payload,
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
        return [message for message in messages.values()]

    monkeypatch.setattr(mock_redis, "zrange", CoroutineMock(return_value=msg_queue))
    monkeypatch.setattr(mock_redis, "mget", _mget)

    msgs = await queue.inspect_all_messages_for_key(key)
    assert len(msgs) == len(expected)
    for i in range(len(expected)):
        assert msgs[i] == expected[i]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("msg_queue", "messages"),
    [
        ([], {}),
        (
            ["1", "2", "3"],
            {
                "1": OutboundMessage(payload="1", enc_payload=b"enc_1").enc_payload,
                "2": OutboundMessage(payload="2", enc_payload=b"enc_2").enc_payload,
                "3": OutboundMessage(payload="3", enc_payload=b"enc_3").enc_payload,
            },
        ),
    ],
)
async def test_remove_messages_for_key(
    queue: RedisPersistedQueue,
    key: str,
    msg_queue: list,
    messages: Dict[str, bytes],
    mock_redis: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    msg: bytes,
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
    del_mock = CoroutineMock()
    monkeypatch.setattr(mock_redis, "zrange", CoroutineMock(return_value=msg_queue))
    monkeypatch.setattr(mock_redis, "delete", del_mock)

    for msg in list(messages.values()):
        await queue.remove_messages_for_key(key, msg)
        if msg_queue == []:
            del_mock.assert_not_called()
        else:
            del_mock.assert_called()
