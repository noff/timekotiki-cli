import os
from pathlib import Path

import av
import numpy as np
import pytest

from tests.conftest import make_wav
from timekotiki.errors import (
    InputUnavailableError,
    NoAudioError,
    UnsupportedFormatError,
)
from timekotiki.media import probe


def make_video_only(path: Path) -> Path:
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width = 32
        stream.height = 32
        stream.pix_fmt = "yuv420p"
        for _ in range(10):
            frame = av.VideoFrame.from_ndarray(np.zeros((32, 32, 3), dtype=np.uint8), "rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InputUnavailableError, match="not found"):
        probe(str(tmp_path / "missing.mp4"))


def test_directory_is_not_a_file(tmp_path: Path) -> None:
    with pytest.raises(InputUnavailableError):
        probe(str(tmp_path))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_unreadable_file(tmp_path: Path) -> None:
    path = make_wav(tmp_path / "a.wav", 1.0)
    path.chmod(0o000)
    try:
        with pytest.raises(InputUnavailableError):
            probe(str(path))
    finally:
        path.chmod(0o600)


@pytest.mark.parametrize("url", ["https://youtu.be/abc", "file:///tmp/a.mp4", "s3://b/k.mp4"])
def test_url_rejected(url: str) -> None:
    with pytest.raises(InputUnavailableError, match="only local files are supported"):
        probe(url)


def test_text_file_is_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "notes.mp4"
    path.write_text("definitely not a video\n" * 100)
    with pytest.raises(UnsupportedFormatError):
        probe(str(path))


def test_wav_is_probed(tmp_path: Path) -> None:
    path = make_wav(tmp_path / "a.wav", 2.5)
    source = probe(str(path))
    assert source.path == path.resolve()
    assert source.has_audio is True
    assert source.duration == pytest.approx(2.5, abs=0.05)


def test_video_without_audio(tmp_path: Path) -> None:
    path = make_video_only(tmp_path / "silent.mp4")
    with pytest.raises(NoAudioError):
        probe(str(path))
