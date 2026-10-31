"""Deterministic chapter rules that do not depend on the LLM (data-model.md invariants)."""

from __future__ import annotations

import math
from dataclasses import replace

from timekotiki.models import Boundary, ChapterDraft, Options, Transcript

PLATFORM_MIN_CHAPTERS = 3
PLATFORM_MIN_SECONDS = 10.0


def build_chapters(
    transcript: Transcript, boundaries: list[Boundary], options: Options
) -> tuple[list[ChapterDraft], list[str]]:
    duration = transcript.duration
    hints: dict[int, str] = {0: ""}
    for b in boundaries:
        if b.segment_index not in hints or not hints[b.segment_index]:
            hints[b.segment_index] = b.topic_hint

    starts: list[tuple[float, str]] = []
    for index in sorted(hints):
        start = 0.0 if index == 0 else transcript.segments[index].start
        if start >= duration:
            continue
        if starts and math.floor(start) == math.floor(starts[-1][0]):
            continue
        starts.append((start, hints[index]))

    drafts = [
        ChapterDraft(start=start, end=nxt[0] if nxt else duration, topic_hint=hint)
        for (start, hint), nxt in zip(starts, [*starts[1:], None], strict=True)
    ]
    drafts = _merge_short(drafts, options.min_chapter)
    drafts = _enforce_max_chapters(drafts, options.max_chapters)
    return drafts, _warnings(drafts)


def _merge(drafts: list[ChapterDraft], i: int) -> list[ChapterDraft]:
    """Merge chapter `i` with chapter `i + 1`, keeping the start and hint of `i`."""
    merged = replace(drafts[i], end=drafts[i + 1].end)
    return [*drafts[:i], merged, *drafts[i + 2 :]]


def _merge_short(drafts: list[ChapterDraft], min_chapter: float) -> list[ChapterDraft]:
    while len(drafts) > 1:
        short = next((i for i, d in enumerate(drafts) if d.end - d.start < min_chapter), None)
        if short is None:
            break
        # The first chapter absorbs the next one so that it keeps starting at 00:00;
        # any other short chapter becomes the tail of the previous one.
        drafts = _merge(drafts, 0) if short == 0 else _merge(drafts, short - 1)
    return drafts


def _enforce_max_chapters(
    drafts: list[ChapterDraft], max_chapters: int | None
) -> list[ChapterDraft]:
    """Merge the adjacent pair with the smallest combined length until the limit holds."""
    if max_chapters is None:
        return drafts
    while len(drafts) > max_chapters:
        pair = min(range(len(drafts) - 1), key=lambda i: drafts[i + 1].end - drafts[i].start)
        drafts = _merge(drafts, pair)
    return drafts


def _warnings(drafts: list[ChapterDraft]) -> list[str]:
    warnings = []
    if len(drafts) < PLATFORM_MIN_CHAPTERS:
        warnings.append("fewer_than_3_chapters")
    if any(d.end - d.start < PLATFORM_MIN_SECONDS for d in drafts):
        warnings.append("chapter_shorter_than_10s")
    if len(drafts) == 1:
        warnings.append("single_topic")
    return warnings
