"""Stage progress on stderr. Never writes colour or other escape codes."""

from __future__ import annotations

from typing import TextIO

STAGES: dict[str, str] = {
    "probe": "Reading input",
    "transcribe": "Transcribing speech",
    "segment": "Finding topics",
    "title": "Writing titles",
}


class Progress:
    def __init__(self, stream: TextIO, *, is_tty: bool, quiet: bool) -> None:
        self._stream = stream
        self._is_tty = is_tty
        self._quiet = quiet
        self._current: str | None = None
        self._line_open = False

    def _label(self, name: str) -> str:
        number = list(STAGES).index(name) + 1
        return f"[{number}/{len(STAGES)}] {STAGES[name]}"

    def _finish_line(self) -> None:
        if self._line_open:
            self._stream.write("\n")
            self._line_open = False

    def stage(self, name: str) -> None:
        if self._quiet:
            return
        self._finish_line()
        self._current = name
        if self._is_tty:
            self._stream.write(f"\r{self._label(name)}...")
            self._line_open = True
        else:
            self._stream.write(f"{self._label(name)}...\n")
        self._stream.flush()

    def skip(self, name: str, reason: str = "cached") -> None:
        if self._quiet:
            return
        self._finish_line()
        self._current = None
        self._stream.write(f"{self._label(name)}: skipped ({reason})\n")
        self._stream.flush()

    def update(self, fraction: float) -> None:
        if self._quiet or not self._is_tty or self._current is None:
            return
        percent = round(min(max(fraction, 0.0), 1.0) * 100)
        self._stream.write(f"\r{self._label(self._current)}... {percent:3d}%")
        self._line_open = True
        self._stream.flush()

    def done(self) -> None:
        if self._quiet:
            return
        self._finish_line()
        self._current = None
        self._stream.flush()
