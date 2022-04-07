import logging

import asyncio
import aioredis
import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_set_get(redis_connection):
    """Test our ability to set values on a redis connection."""
    await redis_connection.set("some-key", "some-value")
    value = await redis_connection.get("some-key")
    assert value == "some-value"
