"""Timecode formatting and result renderers (text, JSON, WebVTT)."""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from timekotiki.models import ChapterResult


def format_timecode(seconds: float) -> str:
    """`MM:SS` below one hour, `H:MM:SS` from one hour on; floored to whole seconds."""
    total = math.floor(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def render_text(result: ChapterResult) -> str:
    return "".join(f"{ch.timecode} {ch.title}\n" for ch in result.chapters)


SCHEMA_VERSION = 1


def render_json(result: ChapterResult) -> str:
    document = {
        "schema_version": SCHEMA_VERSION,
        "source": result.source.name,
        "duration": round(result.duration, 3),
        "speech_language": result.speech_language,
        "title_language": result.title_language,
        "chapters": [
            {
                "start": round(ch.start, 3),
                "end": round(ch.end, 3),
                "timecode": ch.timecode,
                "title": ch.title,
            }
            for ch in result.chapters
        ],
        "options": {
            "min_chapter": result.options.min_chapter,
            "max_chapters": result.options.max_chapters,
            "asr_model": result.options.asr_model,
            "llm_model": result.options.llm_model,
        },
        "warnings": list(result.warnings),
        "transcript_cached": result.transcript_cached,
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _vtt_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def render_vtt(result: ChapterResult) -> str:
    cues = [
        f"{n}\n{_vtt_timestamp(ch.start)} --> {_vtt_timestamp(ch.end)}\n{ch.title}\n"
        for n, ch in enumerate(result.chapters, start=1)
    ]
    return "WEBVTT\n\n" + "\n".join(cues)


RENDERERS = {"text": render_text, "json": render_json, "vtt": render_vtt}
