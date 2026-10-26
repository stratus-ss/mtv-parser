from argparse import ArgumentTypeError
from datetime import datetime, timedelta, timezone

import pytest

from mtv_parser.utils import as_naive_utc, string_to_datetime

_INVALID_DATE = r"Invalid date format\. Expected YYYY-MM-DD"


def test_as_naive_utc_zulu_blank_and_none():
    parsed = as_naive_utc("2026-10-09T18:17:29Z")
    assert parsed == datetime(2026, 10, 9, 18, 17, 29)
    assert as_naive_utc(None) is None
    assert as_naive_utc("") is None
    assert as_naive_utc("not-a-time") is None


def test_as_naive_utc_datetime_passthrough_and_aware():
    naive = datetime(2026, 10, 9, 18, 17, 29)
    assert as_naive_utc(naive) == naive
    aware = datetime(2026, 9, 27, 3, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert as_naive_utc(aware) == datetime(2026, 9, 27, 8, 0)


def test_string_to_datetime_midnight():
    assert string_to_datetime("2026-09-27") == datetime(2026, 9, 27)


def test_string_to_datetime_rejects_slashes():
    with pytest.raises(ArgumentTypeError, match=_INVALID_DATE):
        string_to_datetime("09/27/2026")


def test_string_to_datetime_rejects_compact():
    with pytest.raises(ArgumentTypeError):
        string_to_datetime("20260927")


def test_string_to_datetime_rejects_impossible_day():
    with pytest.raises(ArgumentTypeError):
        string_to_datetime("2026-02-31")
