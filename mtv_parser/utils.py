"""Datetime helpers shared across the CLI."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone


def as_naive_utc(value: datetime | str | None) -> datetime | None:
    """Return a naive UTC datetime, or None when value is missing or invalid.

    A naive datetime is returned unchanged. An aware datetime is converted to UTC
    and then stored without tzinfo. An ISO string is parsed first, including a
    trailing Z. None, a blank string, and an unparseable string return None.
    """
    if value is None:
        return None
    if isinstance(value, str):
        if value == "":
            return None
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value
    utc_value = value.astimezone(timezone.utc)
    return utc_value.replace(tzinfo=None)


def string_to_datetime(value: str) -> datetime:
    """Parse a CLI date flag value (YYYY-MM-DD) into a naive midnight datetime."""
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format. Expected YYYY-MM-DD, got {value}")
