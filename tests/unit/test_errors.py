import pytest

from timekotiki import errors
from timekotiki.errors import (
    EXIT_INTERRUPTED,
    BackendUnavailableError,
    InputUnavailableError,
    NoAudioError,
    NoSpeechError,
    OutputConflictError,
    ProcessingError,
    UnsupportedFormatError,
    UsageError,
    exit_code_for,
    format_error,
)


@pytest.mark.parametrize(
    ("exc_type", "code"),
    [
        (UsageError, 2),
        (InputUnavailableError, 3),
        (UnsupportedFormatError, 4),
        (NoAudioError, 5),
        (NoSpeechError, 5),
        (BackendUnavailableError, 6),
        (ProcessingError, 7),
        (OutputConflictError, 8),
    ],
)
def test_exit_codes_match_contract(exc_type: type[errors.TimekotikiError], code: int) -> None:
    assert exit_code_for(exc_type("boom")) == code
    assert errors.EXIT_CODES[exc_type] == code


def test_interrupted_code() -> None:
    assert EXIT_INTERRUPTED == 130


def test_format_error_without_hint() -> None:
    assert format_error(InputUnavailableError("file not found: x.mp4")) == (
        "timekotiki: error: file not found: x.mp4"
    )


def test_format_error_with_hint() -> None:
    exc = BackendUnavailableError("ASR model is not installed", hint="timekotiki models pull")
    assert format_error(exc) == (
        "timekotiki: error: ASR model is not installed\nhint: timekotiki models pull"
    )
