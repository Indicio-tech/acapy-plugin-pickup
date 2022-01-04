"""Test messages."""

import pytest
import json
from datetime import datetime
from acapy_plugin_pickup.protocol.status import Status


def test_create_status():
    status = Status(message_count=10)
    assert status.type == Status.message_type
    assert status.message_count == 10
    assert status.newest_time is None
    assert status.recipient_key is None
    assert status.duration_waited is None
    assert status.newest_time is None
    assert status.oldest_time is None
    assert status.total_size is None

    now = datetime.now()
    with pytest.raises(ValueError):
        status = Status(message_count=0, newest_time=now)

    status = Status(message_count=0, newest_time=now.isoformat())
    assert status.newest_time == now
    serialized = json.loads(status.json())
    assert serialized["newest_time"]
    assert serialized["newest_time"] == now.isoformat()
