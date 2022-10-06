"""Test in memory queue for undelivered messages."""
import pytest

from acapy_plugin_pickup.undelivered_queue.in_memory import InMemoryQueue


@pytest.fixture
def queue():
    yield InMemoryQueue()


@pytest.mark.asyncio
async def test_add_message(queue: InMemoryQueue):
    """Test adding a message."""
    await queue.add_message("key", b"msg")
    assert queue.queue_by_key == {"key": [b"msg"]}


@pytest.mark.asyncio
async def test_has_message_for_key(queue: InMemoryQueue):
    """Test has message for key."""
    await queue.add_message("key", b"msg")
    assert await queue.has_message_for_key("key")


@pytest.mark.asyncio
async def test_message_count_for_key(queue: InMemoryQueue):
    """Test message count for key."""
    assert await queue.message_count_for_key("key") == 0
    await queue.add_message("key", b"msg")
    assert await queue.message_count_for_key("key") == 1
    await queue.add_message("key", b"msg")
    assert await queue.message_count_for_key("key") == 2


@pytest.mark.asyncio
async def test_get_messages_for_key(queue: InMemoryQueue):
    """Test get messages for key."""
    assert await queue.get_messages_for_key("key") == []
    await queue.add_message("key", b"msg")
    assert await queue.get_messages_for_key("key") == [b"msg"]
    await queue.add_message("key", b"msg")
    assert await queue.get_messages_for_key("key") == [b"msg", b"msg"]
    assert await queue.get_messages_for_key("key", 0) == []
    assert await queue.get_messages_for_key("key", 1) == [b"msg"]
    assert await queue.get_messages_for_key("key", 2) == [b"msg", b"msg"]


@pytest.mark.asyncio
async def test_remove_messages_for_key(queue: InMemoryQueue):
    """Test remove messages for key."""
    await queue.remove_messages_for_key("key", [b"non-existant"])
    await queue.add_message("key", b"msg")
    await queue.remove_messages_for_key("key", [queue.message_id_for_outbound(b"msg")])
    assert not queue.queue_by_key["key"]
