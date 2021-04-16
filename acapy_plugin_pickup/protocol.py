"""Pickup Protocol."""

from typing import Optional

from datetime import datetime
from pydantic import validator
from .acapy import AgentMessage

PROTOCOL = "https://didcomm.org/messagepickup/2.0/status-request"


class StatusRequest(AgentMessage):
    """StatusRequest message."""

    recipient_key: Optional[str] = None


class Status(AgentMessage):
    """Status message."""

    message_count: int
    recipient_key: Optional[str] = None
    duration_waited: Optional[int] = None
    newest_time: Optional[datetime] = None
    oldest_time: Optional[datetime] = None
    total_size: Optional[int] = None

    class Config:
        """Model config."""

        json_encoders = {
            datetime: lambda value: value.isoformat(),
        }

    @validator("newest_time", "oldest_time", pre=True)
    @classmethod
    def _validate_time_format(cls, value: str):
        """Validate timestamps came in as ISO"""
        return datetime.fromisoformat(value)
