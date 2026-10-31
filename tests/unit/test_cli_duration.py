import argparse

import pytest

from tests.conftest import DepsFactory
from timekotiki.cli import parse_duration, parse_language


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [("90", 90.0), ("1m30s", 90.0), ("5m", 300.0), ("1h", 3600.0), ("10s", 10.0), ("12.5", 12.5)],
)
def test_parse_duration(raw: str, seconds: float) -> None:
    assert parse_duration(raw) == seconds


@pytest.mark.parametrize("raw", ["abc", "0", "5s", "", "1m30", "-5m"])
def test_parse_duration_rejects(raw: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_duration(raw)


@pytest.mark.parametrize("raw", ["ru", "en", "fil"])
def test_parse_language(raw: str) -> None:
    assert parse_language(raw) == raw


@pytest.mark.parametrize("raw", ["RU", "russian", "r", "ru-RU"])
def test_parse_language_rejects(raw: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_language(raw)


@pytest.mark.parametrize(
    "argv",
    [
        ["--min-chapter", "5s"],
        ["--max-chapters", "0"],
        ["--max-chapters", "x"],
        ["--title-language", "English"],
        ["--speech-language", "RU"],
    ],
)
def test_invalid_options_are_usage_errors(make_deps: DepsFactory, argv: list[str]) -> None:
    env = make_deps()
    assert env.main(["generate", *argv, "talk.mp4"]) == 2
    assert env.stderr.getvalue().startswith("timekotiki: error:")
