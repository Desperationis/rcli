import pytest
from rcli.utils import format_size, format_date


@pytest.mark.parametrize(
    "size_bytes, expected",
    [
        (0, "0 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024 * 1024, "1.0 MB"),
        (1024 * 1024 * 1024, "1.0 GB"),
        (500, "500 B"),
        (None, "unknown"),
        (-1, "unknown"),
    ],
)
def test_format_size(size_bytes, expected):
    assert format_size(size_bytes) == expected


@pytest.mark.parametrize(
    "iso_str, expected",
    [
        ("2024-01-15T10:30:00Z", "2024-01-15 10:30"),
        ("2024-01-15T10:30:00+00:00", "2024-01-15 10:30"),
        ("2024-06-01T00:00:00Z", "2024-06-01 00:00"),
        ("not-a-date", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_format_date(iso_str, expected):
    assert format_date(iso_str) == expected
