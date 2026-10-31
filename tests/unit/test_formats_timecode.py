import pytest

from timekotiki.formats import format_timecode


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.0, "00:00"),
        (0.999, "00:00"),
        (59.0, "00:59"),
        (252.9, "04:12"),
        (3599.99, "59:59"),
        (3600.0, "1:00:00"),
        (3750.0, "1:02:30"),
        (36000.0, "10:00:00"),
    ],
)
def test_format_timecode(seconds: float, expected: str) -> None:
    assert format_timecode(seconds) == expected
