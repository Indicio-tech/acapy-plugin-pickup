"""Validation helpers."""

from datetime import datetime
from dateutil import parser
from pydantic.class_validators import validator


class ISODateTime(datetime):
    """Custom field for ISO formatted datetime."""

    @classmethod
    def __get_validators__(cls):
        """Yield validators."""
        yield cls.validate

    @validator("__root__", pre=True)
    @classmethod
    def validate(cls, value):
        """Validate the datetime value as ISO time format."""
        return parser.isoparse(value)
