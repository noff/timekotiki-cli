"""Split a transcript into LLM-sized windows and merge the topic boundaries found in them."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from timekotiki.formats import format_timecode
from timekotiki.models import Boundary, Transcript

WINDOW_SECONDS = 600.0
OVERLAP_SECONDS = 60.0
MERGE_DISTANCE_SECONDS = 30.0


@dataclass(frozen=True)
class Window:
    indices: tuple[int, ...]
    lines: list[str]


def build_windows(
    transcript: Transcript, size: float = WINDOW_SECONDS, overlap: float = OVERLAP_SECONDS
) -> list[Window]:
    """Group segments by start time into windows of `size` seconds overlapping by `overlap`."""
    segments = transcript.segments
    last_start = segments[-1].start
    windows = []
    window_start = 0.0
    while True:
        chosen = [s for s in segments if window_start <= s.start < window_start + size]
        if chosen:
            windows.append(
                Window(
                    indices=tuple(s.index for s in chosen),
                    lines=[f"[{s.index}] {format_timecode(s.start)} {s.text}" for s in chosen],
                )
            )
        if window_start + size > last_start:
            return windows
        window_start += size - overlap


def merge_boundaries(
    transcript: Transcript,
    per_window: Iterable[tuple[Window, list[Boundary]]],
    distance: float = MERGE_DISTANCE_SECONDS,
) -> list[Boundary]:
    """Combine window answers into one sorted list that always starts at segment 0.

    Indices outside their window are dropped; boundaries closer than `distance` seconds
    collapse into the earlier one, which inherits a topic hint if it had none.
    """
    candidates = [
        b
        for window, boundaries in per_window
        for b in boundaries
        if b.segment_index in window.indices
    ]
    candidates.sort(key=lambda b: b.segment_index)
    merged = [Boundary(0)]
    for b in candidates:
        last = merged[-1]
        gap = (
            transcript.segments[b.segment_index].start
            - transcript.segments[last.segment_index].start
        )
        if gap < distance:
            if not last.topic_hint and b.topic_hint:
                merged[-1] = Boundary(last.segment_index, b.topic_hint)
            continue
        merged.append(b)
    return merged
