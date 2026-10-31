"""Validation of the input file."""

from __future__ import annotations

import re
from pathlib import Path

import av

from timekotiki.errors import InputUnavailableError, NoAudioError, UnsupportedFormatError
from timekotiki.models import MediaSource

_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def probe(arg: str) -> MediaSource:
    if _URL.match(arg):
        raise InputUnavailableError(
            f"only local files are supported: {arg}",
            hint="download the video first and pass the path to the file",
        )
    path = Path(arg).expanduser()
    if not path.exists():
        raise InputUnavailableError(f"file not found: {arg}")
    if not path.is_file():
        raise InputUnavailableError(f"not a file: {arg}")
    try:
        with path.open("rb"):
            pass
    except OSError as exc:
        raise InputUnavailableError(f"cannot read {arg}: {exc.strerror}") from exc

    try:
        container = av.open(str(path))
    except av.FFmpegError as exc:
        raise UnsupportedFormatError(f"unsupported or corrupted media file: {arg}") from exc
    with container:
        audio = container.streams.audio
        if not audio:
            raise NoAudioError(f"no audio track in {arg}")
        duration = _duration(container, audio[0])
    if duration is None or duration <= 0:
        raise UnsupportedFormatError(f"cannot determine the duration of {arg}")
    return MediaSource(path=path.resolve(), duration=duration, has_audio=True)


def _duration(container: av.container.InputContainer, stream: av.audio.AudioStream) -> float | None:
    if container.duration is not None:
        return float(container.duration / av.time_base)
    if stream.duration is not None and stream.time_base is not None:
        return float(stream.duration * stream.time_base)
    return None
