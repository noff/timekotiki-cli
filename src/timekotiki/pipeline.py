"""The end-to-end flow: probe → transcribe → segment → title."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import replace

from timekotiki.asr import Transcriber
from timekotiki.cache import TranscriptCache, file_sha256
from timekotiki.llm import ChapterModel, clean_title
from timekotiki.models import (
    Chapter,
    ChapterDraft,
    ChapterResult,
    MediaSource,
    Options,
    Transcript,
)
from timekotiki.postprocess import build_chapters
from timekotiki.progress import Progress
from timekotiki.segmentation import build_windows, merge_boundaries


def run_pipeline(
    arg: str,
    options: Options,
    *,
    probe: Callable[[str], MediaSource],
    transcriber: Transcriber,
    chapter_model: ChapterModel,
    progress: Progress,
    cache: TranscriptCache | None = None,
) -> ChapterResult:
    try:
        progress.stage("probe")
        media = probe(arg)
        chapter_model.is_available()

        sha256 = file_sha256(media.path) if cache is not None else ""
        transcript = None
        if cache is not None and options.use_cache:
            transcript = cache.load(sha256, options.asr_model, options.speech_language)
        cached = transcript is not None
        if transcript is not None:
            progress.skip("transcribe")
        else:
            progress.stage("transcribe")
            transcript = transcriber.transcribe(
                media.path, language=options.speech_language, on_progress=progress.update
            )
            if cache is not None:
                # A cache that cannot be written only costs speed on the next run.
                with contextlib.suppress(OSError):
                    cache.save(sha256, options.speech_language, transcript)
        transcript = replace(transcript, duration=media.duration)

        progress.stage("segment")
        windows = build_windows(transcript)
        answers = []
        for i, window in enumerate(windows, start=1):
            answers.append(
                (window, chapter_model.find_boundaries(window.lines, transcript.language))
            )
            progress.update(i / len(windows))
        boundaries = merge_boundaries(transcript, answers)
        drafts, warnings = build_chapters(transcript, boundaries, options)

        progress.stage("title")
        title_language = options.title_language or transcript.language
        chapters = []
        for i, draft in enumerate(drafts, start=1):
            chapters.append(_title(draft, i, transcript, title_language, chapter_model))
            progress.update(i / len(drafts))
    finally:
        progress.done()

    return ChapterResult(
        source=media.path,
        duration=media.duration,
        speech_language=transcript.language,
        title_language=title_language,
        chapters=tuple(chapters),
        options=options,
        warnings=tuple(warnings),
        transcript_cached=cached,
    )


def _title(
    draft: ChapterDraft,
    number: int,
    transcript: Transcript,
    language: str,
    chapter_model: ChapterModel,
) -> Chapter:
    text = " ".join(s.text for s in transcript.segments if draft.start <= s.start < draft.end)
    title = clean_title(chapter_model.make_title(text, language, draft.topic_hint or None))
    if not title:
        title = clean_title(draft.topic_hint) or f"Chapter {number}"
    return Chapter(start=draft.start, end=draft.end, title=title)
