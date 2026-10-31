"""Immutable domain objects (see data-model.md).

All times are offsets from the start of the media, in seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from timekotiki.formats import format_timecode

MAX_TITLE_LENGTH = 60
MIN_CHAPTER_FLOOR = 10.0


@dataclass(frozen=True)
class MediaSource:
    path: Path
    duration: float
    has_audio: bool


@dataclass(frozen=True)
class TranscriptSegment:
    index: int
    start: float
    end: float
    text: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.start > self.end:
            raise ValueError(f"invalid segment bounds: {self.start}..{self.end}")
        if not self.text.strip():
            raise ValueError("segment text must not be blank")


@dataclass(frozen=True)
class Transcript:
    segments: tuple[TranscriptSegment, ...]
    language: str
    asr_model: str
    duration: float


@dataclass(frozen=True)
class Boundary:
    segment_index: int
    topic_hint: str = ""


@dataclass(frozen=True)
class ChapterDraft:
    """A chapter after post-processing, before it gets its final title."""

    start: float
    end: float
    topic_hint: str = ""


@dataclass(frozen=True)
class Chapter:
    start: float
    end: float
    title: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.title) <= MAX_TITLE_LENGTH:
            raise ValueError(f"title must be 1..{MAX_TITLE_LENGTH} characters: {self.title!r}")
        if "\n" in self.title or "\r" in self.title:
            raise ValueError("title must not contain line breaks")

    @property
    def timecode(self) -> str:
        return format_timecode(self.start)


@dataclass(frozen=True)
class Options:
    min_chapter: float = 60.0
    max_chapters: int | None = None
    title_language: str | None = None
    speech_language: str | None = None
    asr_model: str = "large-v3-turbo"
    llm_model: str = "qwen2.5:7b-instruct"
    use_cache: bool = True

    def __post_init__(self) -> None:
        if self.min_chapter < MIN_CHAPTER_FLOOR:
            raise ValueError(f"min_chapter must be >= {MIN_CHAPTER_FLOOR:g} seconds")
        if self.max_chapters is not None and self.max_chapters < 1:
            raise ValueError("max_chapters must be >= 1")


@dataclass(frozen=True)
class ChapterResult:
    source: Path
    duration: float
    speech_language: str
    title_language: str
    chapters: tuple[Chapter, ...]
    options: Options
    warnings: tuple[str, ...] = field(default=())
    transcript_cached: bool = False
