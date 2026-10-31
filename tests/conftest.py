"""Deterministic fakes for the ASR and LLM backends, plus input factories."""

from __future__ import annotations

import io
import math
import re
import struct
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from timekotiki.cli import Deps, main
from timekotiki.models import Boundary, MediaSource, Transcript, TranscriptSegment

TOPIC_PREFIX = "Тема:"
_LINE = re.compile(r"^\[(\d+)\] \S+ (.*)$")


def make_transcript(
    items: list[tuple[float, str]],
    *,
    language: str = "ru",
    asr_model: str = "large-v3-turbo",
    duration: float | None = None,
) -> Transcript:
    """Build a transcript from consecutive `(seconds, text)` pieces.

    A piece whose text starts with "Тема:" is a topic start for `FakeChapterModel`.
    """
    segments = []
    t = 0.0
    for i, (length, text) in enumerate(items):
        segments.append(TranscriptSegment(index=i, start=t, end=t + length, text=text))
        t += length
    return Transcript(
        segments=tuple(segments),
        language=language,
        asr_model=asr_model,
        duration=duration if duration is not None else t,
    )


def topic_transcript(
    topics: list[tuple[str, float]], *, piece: float = 30.0, language: str = "ru"
) -> Transcript:
    """Transcript with one marked topic start per `(title, seconds)` entry."""
    items: list[tuple[float, str]] = []
    for title, length in topics:
        count = max(1, round(length / piece))
        items.append((length / count, f"{TOPIC_PREFIX} {title}"))
        items.extend((length / count, f"Говорим про {title}, часть {n}") for n in range(1, count))
    return make_transcript(items, language=language)


def make_wav(path: Path, seconds: float, *, silent: bool = True) -> Path:
    rate = 16000
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        if silent:
            w.writeframes(b"\x00\x00" * frames)
        else:
            w.writeframes(
                b"".join(
                    struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * n / rate)))
                    for n in range(frames)
                )
            )
    return path


@dataclass
class FakeTranscriber:
    model_name: str = "large-v3-turbo"
    transcript: Transcript | None = None
    exc: BaseException | None = None
    installed: bool = True
    calls: list[tuple[Path, str | None]] = field(default_factory=list)
    pulled: bool = False

    def transcribe(
        self, path: Path, *, language: str | None, on_progress: Callable[[float], None]
    ) -> Transcript:
        self.calls.append((path, language))
        if self.exc is not None:
            raise self.exc
        assert self.transcript is not None, "FakeTranscriber needs a transcript"
        on_progress(0.5)
        on_progress(1.0)
        return Transcript(
            segments=self.transcript.segments,
            language=language or self.transcript.language,
            asr_model=self.model_name,
            duration=self.transcript.duration,
        )

    def is_installed(self) -> bool:
        return self.installed

    def pull(self, on_progress: Callable[[float], None]) -> None:
        on_progress(1.0)
        self.pulled = True
        self.installed = True


@dataclass
class FakeChapterModel:
    """Starts a topic at every window line whose text begins with "Тема:"."""

    model_name: str = "qwen2.5:7b-instruct"
    available_exc: BaseException | None = None
    installed: bool = True
    windows: list[list[str]] = field(default_factory=list)
    title_calls: list[tuple[str, str, str | None]] = field(default_factory=list)
    pulled: bool = False

    def is_available(self) -> None:
        if self.available_exc is not None:
            raise self.available_exc

    def is_installed(self) -> bool:
        return self.installed

    def pull(self, on_progress: Callable[[float], None]) -> None:
        on_progress(1.0)
        self.pulled = True
        self.installed = True

    def find_boundaries(self, window_lines: list[str], language: str) -> list[Boundary]:
        self.windows.append(window_lines)
        found = []
        for line in window_lines:
            m = _LINE.match(line)
            assert m, f"unexpected window line: {line!r}"
            if m.group(2).startswith(TOPIC_PREFIX):
                found.append(Boundary(int(m.group(1)), m.group(2)[len(TOPIC_PREFIX) :].strip()))
        return found

    def make_title(self, text: str, language: str, topic_hint: str | None) -> str:
        self.title_calls.append((text, language, topic_hint))
        title = topic_hint or "Глава"
        return title if language == "ru" else f"{title} [{language}]"


@dataclass
class CliEnv:
    deps: Deps
    transcriber: FakeTranscriber
    chapter_model: FakeChapterModel
    stdout: io.StringIO
    stderr: io.StringIO
    asr_models: list[str]
    llm_models: list[str]

    def main(self, argv: list[str]) -> int:
        return main(argv, self.deps)


DepsFactory = Callable[..., CliEnv]


@pytest.fixture
def make_deps(tmp_path: Path) -> DepsFactory:
    def factory(
        transcript: Transcript | None = None,
        *,
        media_duration: float | None = None,
        is_tty: bool = False,
        env: Mapping[str, str] | None = None,
        transcriber: FakeTranscriber | None = None,
        chapter_model: FakeChapterModel | None = None,
    ) -> CliEnv:
        fake_asr = transcriber or FakeTranscriber(transcript=transcript)
        fake_llm = chapter_model or FakeChapterModel()
        asr_models: list[str] = []
        llm_models: list[str] = []

        def transcriber_factory(name: str) -> FakeTranscriber:
            asr_models.append(name)
            fake_asr.model_name = name
            return fake_asr

        def chapter_model_factory(name: str, base_url: str) -> FakeChapterModel:
            llm_models.append(name)
            fake_llm.model_name = name
            return fake_llm

        def probe(arg: str) -> MediaSource:
            from timekotiki.media import probe as real_probe

            path = Path(arg)
            if media_duration is None or not path.is_file():
                return real_probe(arg)
            return MediaSource(path=path.resolve(), duration=media_duration, has_audio=True)

        stdout, stderr = io.StringIO(), io.StringIO()
        base_env = {"TIMEKOTIKI_CACHE_DIR": str(tmp_path / "cache")}
        base_env.update(env or {})
        deps = Deps(
            transcriber_factory=transcriber_factory,
            chapter_model_factory=chapter_model_factory,
            stdout=stdout,
            stderr=stderr,
            is_tty=is_tty,
            env=base_env,
            probe=probe,
        )
        return CliEnv(deps, fake_asr, fake_llm, stdout, stderr, asr_models, llm_models)

    return factory


@pytest.fixture
def media_file(tmp_path: Path) -> Callable[..., Path]:
    """A placeholder media file whose duration is supplied via `media_duration`."""

    def factory(name: str = "talk.mp4", content: bytes = b"fake video bytes") -> Path:
        path = tmp_path / name
        path.write_bytes(content)
        return path

    return factory
