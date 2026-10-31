"""Error hierarchy and the exit codes documented in contracts/cli.md."""

from __future__ import annotations

EXIT_OK = 0
EXIT_INTERRUPTED = 130


class TimekotikiError(Exception):
    """Base class for every error the CLI reports to the user."""

    exit_code = 1

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UsageError(TimekotikiError):
    exit_code = 2


class InputUnavailableError(TimekotikiError):
    exit_code = 3


class UnsupportedFormatError(TimekotikiError):
    exit_code = 4


class NoAudioError(TimekotikiError):
    exit_code = 5


class NoSpeechError(TimekotikiError):
    exit_code = 5


class BackendUnavailableError(TimekotikiError):
    exit_code = 6


class ProcessingError(TimekotikiError):
    exit_code = 7


class OutputConflictError(TimekotikiError):
    exit_code = 8


EXIT_CODES: dict[type[TimekotikiError], int] = {
    cls: cls.exit_code
    for cls in (
        UsageError,
        InputUnavailableError,
        UnsupportedFormatError,
        NoAudioError,
        NoSpeechError,
        BackendUnavailableError,
        ProcessingError,
        OutputConflictError,
    )
}


def exit_code_for(exc: TimekotikiError) -> int:
    return exc.exit_code


def format_error(exc: TimekotikiError) -> str:
    text = f"timekotiki: error: {exc.message}"
    if exc.hint:
        text += f"\nhint: {exc.hint}"
    return text
